"""Query systemd timer ActiveState / UnitFileState for a list of units.

Replaces the ``ansible.builtin.command`` + ``register`` +
``results[_i].stdout_lines`` index-aligned matching pattern with a single
structured call that returns a ``state`` dict keyed by unit name.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from ansible.module_utils.basic import AnsibleModule  # ty: ignore[unresolved-import]

DOCUMENTATION = r"""
---
module: systemd_timer_state
short_description: Query systemd timer ActiveState and UnitFileState
description:
  - Runs C(systemctl show) for each supplied unit and returns a structured
    C(state) dict keyed by unit name with C(active_state) and
    C(unit_file_state) fields.
  - Read-only inspection module; never changes system state (C(changed=false)).
  - For user-scope units the module sets C(XDG_RUNTIME_DIR=/run/user/<uid>)
    so C(systemctl --user) can reach the user bus when run via become_user.
options:
  units:
    description:
      - List of full systemd unit names to inspect (including suffix, e.g.
        C(restic-profile-myapp.timer)).
    type: list
    elements: str
    required: true
  scope:
    description:
      - systemd scope to query.
    type: str
    default: system
    choices: [system, user]
  runtime_uid:
    description:
      - Numeric UID of the target user for user-scope queries.
      - Sets C(XDG_RUNTIME_DIR=/run/user/<uid>) so systemctl --user can
        connect to the per-user bus. Ignored when C(scope=system).
    type: str
    default: ''
author:
  - ak1ra
"""

EXAMPLES = r"""
- name: Check timer states
  ak1ra_lab.restic_profile.systemd_timer_state:
    units:
      - restic-profile-myapp.timer
      - restic-profile-prune.timer
  register: timer_state

- name: Stop an active timer
  ansible.builtin.systemd_service:
    name: "{{ item }}"
    state: stopped
    enabled: false
  loop: "{{ timer_state.state.keys() | list }}"
  when: >-
    timer_state.state[item].active_state == 'active' or
    timer_state.state[item].unit_file_state == 'enabled'
"""

RETURN = r"""
state:
  description: Per-unit state mapping.
  returned: always
  type: dict
  contains:
    <unit_name>:
      description: State for one unit.
      type: dict
      contains:
        active_state:
          description: systemd ActiveState property value.
          type: str
          sample: active
        unit_file_state:
          description: systemd UnitFileState property value.
          type: str
          sample: enabled
        rc:
          description: Return code from systemctl for this unit.
          type: int
          sample: 0
"""


def _query_unit(
    module: AnsibleModule, unit: str, scope: str, runtime_uid: str
) -> dict[str, Any]:
    """Run ``systemctl show`` for one unit and parse its properties."""
    cmd: list[str] = ["systemctl"]
    env: dict[str, str] | None = None
    if scope == "user":
        cmd.append("--user")
        if runtime_uid:
            env = dict(os.environ)
            env["XDG_RUNTIME_DIR"] = f"/run/user/{runtime_uid}"
    cmd.extend(["show", "--property=ActiveState", "--property=UnitFileState", unit])

    proc = subprocess.run(  # noqa: S603 - cmd built from trusted params
        cmd, capture_output=True, text=True, env=env, check=False
    )

    active_state = ""
    unit_file_state = ""
    for line in proc.stdout.splitlines():
        if line.startswith("ActiveState="):
            active_state = line[len("ActiveState=") :]
        elif line.startswith("UnitFileState="):
            unit_file_state = line[len("UnitFileState=") :]

    return {
        "active_state": active_state,
        "unit_file_state": unit_file_state,
        "rc": proc.returncode,
    }


def main() -> None:
    module = AnsibleModule(
        argument_spec={
            "units": {"type": "list", "elements": "str", "required": True},
            "scope": {
                "type": "str",
                "default": "system",
                "choices": ["system", "user"],
            },
            "runtime_uid": {"type": "str", "default": ""},
        },
        supports_check_mode=True,
    )

    units = module.params["units"]
    scope = module.params["scope"]
    runtime_uid = module.params["runtime_uid"]

    state: dict[str, dict[str, Any]] = {}
    for unit in units:
        state[unit] = _query_unit(module, unit, scope, runtime_uid)

    module.exit_json(changed=False, state=state)


if __name__ == "__main__":
    main()
