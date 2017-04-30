# Copyright 2017, Development Gateway, Inc.
# This file is part of lia, see COPYING.

from setuptools import setup

setup(
        name = "lia",
        version = "0.1",
        license = "GPLv3+",
        description = "LDAP Inventory for Ansible",
        author = "Development Gateway",
        python_requires = ">= 3.4",
        packages = ["lia"],
        install_requires = [
            "ldap3 >= 2.2.2"
            ],
        entry_points = {
            "console_scripts": [
                "lia = lia.main:main"
                ]
            }
        )
