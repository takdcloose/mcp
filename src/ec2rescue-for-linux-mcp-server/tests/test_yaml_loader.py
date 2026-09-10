# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for loading ec2rl module definitions from YAML."""

from awslabs.ec2rescue_for_linux_mcp_server.yaml_loader import (
    _module_from_yaml_doc,
)


class TestModuleFromYamlDoc:
    """A single bad definition must not build an unsafe module or crash."""

    def test_unsafe_arg_key_yields_none(self):
        """A module whose optional key has metacharacters is dropped (None)."""
        doc = {'name': 'evil', 'constraint': {'optional': 'x;id'}}
        assert _module_from_yaml_doc(doc) is None

    def test_leading_hyphen_arg_key_yields_none(self):
        """A leading-hyphen arg key is dropped rather than built."""
        doc = {'name': 'evil', 'constraint': {'required': '-flag'}}
        assert _module_from_yaml_doc(doc) is None

    def test_valid_doc_builds_module(self):
        """A well-formed definition builds a module with parsed arg keys."""
        doc = {
            'name': 'top',
            'constraint': {'optional': 'times since'},
        }
        module = _module_from_yaml_doc(doc)
        assert module is not None
        assert module.name == 'top'
        assert module.optional_args == ['times', 'since']

    def test_untrusted_helptext_is_sanitized(self):
        """The doc's helptext is sanitized when the module is built."""
        doc = {
            'name': 'top',
            'helptext': 'x' * 5000 + '\x00',
        }
        module = _module_from_yaml_doc(doc)
        assert module is not None
        assert len(module.helptext) <= 500
        assert '\x00' not in module.helptext
