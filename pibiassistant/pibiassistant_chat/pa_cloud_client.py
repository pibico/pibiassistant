# pibiAssistant - Cloud Client (retired)
# Copyright (C) 2025 Paul Clinton
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""PA Cloud was retired; AIDA runs natively on the AIDA API.

Only the import name survives, so code and tests that still resolve
``get_pa_cloud_client`` keep working. It never returns a client.
"""

__all__ = ["get_pa_cloud_client"]


def get_pa_cloud_client() -> None:
    """Always None: there is no PA Cloud service to talk to."""
    return None
