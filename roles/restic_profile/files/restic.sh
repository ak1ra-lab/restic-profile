#!/usr/bin/env bash

set -o errexit -o nounset

readonly config_dir="/etc/restic-profile"

print_usage() {
    cat <<'EOF'
Usage: restic.sh PROFILE [restic args...]
       restic.sh --list
EOF
}

list_profiles() {
    declare -a env_files=()
    local env_file
    local profile_name

    if [[ ! -d "${config_dir}" ]]; then
        return 1
    fi

    readarray -t env_files < <(
        find "${config_dir}" -maxdepth 1 -type f -name 'restic-profile-*.env' | sort
    )

    if [[ "${#env_files[@]}" -eq 0 ]]; then
        return 1
    fi

    for env_file in "${env_files[@]}"; do
        profile_name="${env_file##*/restic-profile-}"
        profile_name="${profile_name%.env}"
        printf '%s\n' "${profile_name}"
    done
}

print_available_profiles() {
    printf "Available profiles:\n" >&2
    if ! list_profiles >&2; then
        printf "  (none)\n" >&2
    fi
}

case "${1:-}" in
    -h | --help)
        print_usage
        exit 0
        ;;
    --list)
        list_profiles
        exit 0
        ;;
    "")
        print_usage >&2
        print_available_profiles
        exit 64
        ;;
esac

profile_name="${1}"
shift

env_file="${config_dir}/restic-profile-${profile_name}.env"
if [[ ! -f "${env_file}" ]]; then
    printf "Profile env file not found: %s\n" "${env_file}" >&2
    print_available_profiles
    exit 1
fi

if [[ ! -r "${env_file}" ]]; then
    printf "Profile env file is not readable: %s\n" "${env_file}" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "${env_file}"

restic_cmd="${RESTIC_PROFILE_RESTIC_BINARY:-restic}"

if [[ "${restic_cmd}" == "restic" ]] && ! command -v "${restic_cmd}" >/dev/null 2>&1; then
    if [[ -x "/usr/local/bin/restic" ]]; then
        restic_cmd="/usr/local/bin/restic"
    elif [[ -x "/usr/bin/restic" ]]; then
        restic_cmd="/usr/bin/restic"
    fi
fi

exec "${restic_cmd}" "$@"
