#!/usr/bin/env python3
"""
Test Prometheus remote write with backdated metrics.

This script experiments with different approaches to send historical (backdated)
DORA metrics to Prometheus and verify they can be queried at the correct timestamps.

Context: Backfill approach imports data but queries don't return historical metrics.
Goal: Determine if remote write provides a queryable alternative.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Optional

import requests


class PrometheusRemoteWriteTester:
    """Test different methods of sending backdated metrics to Prometheus."""

    def __init__(self, prometheus_url: str, days_back: int = 30):
        self.prometheus_url = prometheus_url.rstrip("/")
        self.days_back = days_back
        self.past_timestamp = time.time() - (days_back * 86400)
        self.past_timestamp_ms = int(self.past_timestamp * 1000)

    def test_approach_1_openmetrics_text(self) -> bool:
        """
        Attempt 1: Try POSTing OpenMetrics text format to various endpoints.

        Prometheus v3.x might have text import endpoints. This is the simplest
        approach if it works.
        """
        print(f"\n{'=' * 70}")
        print("APPROACH 1: OpenMetrics Text Format")
        print(f"{'=' * 70}\n")

        # Generate OpenMetrics format with explicit timestamp
        metrics_data = f"""# TYPE deploy_timestamp_test gauge
# HELP deploy_timestamp_test Test backdated deploy timestamp
deploy_timestamp_test{{app="/test-app/",image_sha="sha256:test123",exported_namespace="test-ns"}} {self.past_timestamp} {self.past_timestamp_ms}
# EOF
"""

        print(f"Metric timestamp: {datetime.fromtimestamp(self.past_timestamp)} ({self.days_back} days ago)")
        print(f"Metric value: {self.past_timestamp}")
        print(f"\nOpenMetrics payload:\n{metrics_data}")

        # Try potential text ingestion endpoints
        test_endpoints = [
            "/api/v1/import/prometheus",  # VictoriaMetrics-style endpoint (may exist in v3.x)
            "/api/v1/import",
            "/federate",  # Sometimes accepts POST in Prometheus-compatible systems
        ]

        for endpoint in test_endpoints:
            url = f"{self.prometheus_url}{endpoint}"
            print(f"\nTrying endpoint: {endpoint}")

            try:
                response = requests.post(
                    url,
                    data=metrics_data,
                    headers={"Content-Type": "text/plain"},
                    timeout=10,
                )

                print(f"  Status: {response.status_code}")
                if response.status_code in (200, 201, 204):
                    print(f"  ✅ Success! Endpoint accepted the data")
                    print(f"  Response: {response.text[:200]}")
                    return True
                else:
                    print(f"  ❌ Failed: {response.text[:200]}")

            except Exception as e:
                print(f"  ❌ Error: {e}")

        print("\n❌ Approach 1 failed: No text import endpoint found")
        return False

    def test_approach_2_push_gateway_style(self) -> bool:
        """
        Attempt 2: Try Prometheus Push Gateway protocol.

        Uses the /metrics/job/<job>/instance/<instance> endpoint pattern.
        This is less likely to work with backdated timestamps.
        """
        print(f"\n{'=' * 70}")
        print("APPROACH 2: Push Gateway Protocol")
        print(f"{'=' * 70}\n")

        # Push Gateway doesn't support explicit timestamps in standard usage
        # But we can try and see what happens
        print("⚠️  Note: Push Gateway typically doesn't support backdated timestamps")
        print("Skipping this approach as it's unlikely to work for our use case\n")
        return False

    def test_approach_3_remote_write_protobuf(self) -> bool:
        """
        Attempt 3: Use proper Prometheus remote write protocol.

        This requires protobuf encoding and snappy compression.
        We'll try using requests to send a simple protobuf payload.
        """
        print(f"\n{'=' * 70}")
        print("APPROACH 3: Remote Write Protocol (Protobuf)")
        print(f"{'=' * 70}\n")

        try:
            # Try importing protobuf libraries
            from google.protobuf import timestamp_pb2
            from snappy import compress

            print("✅ Protobuf libraries available")
            print("⚠️  Full remote write implementation requires prometheus_remote_write library")
            print("This is complex - skipping detailed implementation for now\n")

            # For a full implementation, we'd need:
            # 1. prometheus_remote_write library OR hand-crafted protobuf
            # 2. Create WriteRequest with TimeSeries containing samples
            # 3. Serialize to protobuf, compress with snappy
            # 4. POST to /api/v1/write with Content-Encoding: snappy

            return False

        except ImportError as e:
            print(f"❌ Missing libraries: {e}")
            print("Would need: pip install protobuf snappy prometheus-remote-write\n")
            return False

    def verify_data_queryable(self) -> bool:
        """
        Verify if the backdated metric is queryable in Prometheus.

        This is the CRITICAL test - data must be both imported AND queryable.
        """
        print(f"\n{'=' * 70}")
        print("VERIFICATION: Query Historical Data")
        print(f"{'=' * 70}\n")

        metric_name = "deploy_timestamp_test"
        labels = '{app="/test-app/"}'

        # Test 1: Query at the backdated timestamp
        print(f"Test 1: Query at historical time ({self.days_back} days ago)")
        print(f"  Timestamp: {datetime.fromtimestamp(self.past_timestamp)}")

        query_url = f"{self.prometheus_url}/api/v1/query"
        params = {
            "query": f"{metric_name}{labels}",
            "time": self.past_timestamp,
        }

        try:
            response = requests.get(query_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                results = data.get("data", {}).get("result", [])
                if results:
                    print(f"  ✅ SUCCESS! Found {len(results)} result(s)")
                    for result in results:
                        value = result.get("value", [None, None])[1]
                        print(f"    Value: {value}")
                        print(f"    Labels: {result.get('metric')}")
                    print("\n✅ Historical data IS QUERYABLE!")
                    return True
                else:
                    print("  ❌ No results found at historical timestamp")
                    print(f"  Response: {json.dumps(data, indent=2)}")
            else:
                print(f"  ❌ Query failed: {data}")

        except Exception as e:
            print(f"  ❌ Error querying: {e}")

        # Test 2: Range query
        print(f"\nTest 2: Range query spanning historical period")
        start_time = self.past_timestamp - (5 * 86400)  # 5 days before
        end_time = self.past_timestamp + (5 * 86400)  # 5 days after

        print(f"  Start: {datetime.fromtimestamp(start_time)}")
        print(f"  End: {datetime.fromtimestamp(end_time)}")

        range_url = f"{self.prometheus_url}/api/v1/query_range"
        params = {
            "query": f"{metric_name}{labels}",
            "start": start_time,
            "end": end_time,
            "step": "1d",
        }

        try:
            response = requests.get(range_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "success":
                results = data.get("data", {}).get("result", [])
                if results:
                    values = results[0].get("values", [])
                    print(f"  ✅ Found {len(values)} data points in range")
                    for ts, val in values[:3]:  # Show first 3
                        print(f"    {datetime.fromtimestamp(ts)}: {val}")
                    return True
                else:
                    print("  ❌ No results in range query")
            else:
                print(f"  ❌ Range query failed: {data}")

        except Exception as e:
            print(f"  ❌ Error in range query: {e}")

        print("\n❌ VERIFICATION FAILED: Data not queryable")
        return False

    def run_all_tests(self) -> bool:
        """Run all test approaches and verification."""
        print(f"\n{'#' * 70}")
        print(f"# Prometheus Remote Write Test - {self.days_back} Days Back")
        print(f"# Target: {self.prometheus_url}")
        print(f"# Timestamp: {datetime.fromtimestamp(self.past_timestamp)}")
        print(f"{'#' * 70}")

        # Try approaches in order
        success = False

        # Approach 1: Simple text format
        if self.test_approach_1_openmetrics_text():
            success = True

        # If text format didn't work, note that we'd need to try protobuf
        if not success:
            print("\n💡 Next steps:")
            print("  - Install: pip install prometheus-remote-write protobuf snappy")
            print("  - Implement proper protobuf remote write")
            print("  - Configure Prometheus OOO window if needed")

        # Always try to verify (in case data was already there from previous test)
        print("\n" + "=" * 70)
        print("Attempting to query regardless of import result...")
        print("=" * 70)

        queryable = self.verify_data_queryable()

        return success and queryable


def main():
    parser = argparse.ArgumentParser(
        description="Test Prometheus remote write with backdated metrics"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:9090",
        help="Prometheus URL (default: http://localhost:9090)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=30,
        help="How many days to backdate the metric (default: 30)",
    )

    args = parser.parse_args()

    tester = PrometheusRemoteWriteTester(args.url, args.days_back)
    success = tester.run_all_tests()

    print(f"\n{'#' * 70}")
    if success:
        print("# ✅ TEST PASSED: Remote write works for backdated metrics!")
        print("# Data was successfully imported AND is queryable")
    else:
        print("# ❌ TEST FAILED: Remote write did not work as expected")
        print("# Either import failed or data is not queryable")
    print(f"{'#' * 70}\n")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
