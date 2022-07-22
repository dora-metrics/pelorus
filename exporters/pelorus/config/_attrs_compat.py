"""
Re-exports attrs.NOTHING with fixed typing,
at least until [PR 983](https://github.com/python-attrs/attrs/pull/983) lands.
"""
import attrs

NOTHING = attrs.NOTHING

Factory = attrs.Factory
