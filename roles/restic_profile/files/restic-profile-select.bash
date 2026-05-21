# shellcheck shell=bash
# restic-profile-select.bash
#
# Source this file in your ~/.bashrc to define the restic-profile-select
# function, which shows an interactive menu and injects the chosen profile's
# environment variables into the current shell session:
#
#   test -f /etc/restic-profile/restic-profile-select.bash && \
#       source /etc/restic-profile/restic-profile-select.bash
#
# Usage: restic-profile-select
#
# After selection, RESTIC_* variables are exported in the current shell so
# plain `restic` commands work directly with full shell completion intact.

restic-profile-select() {
    local config_dir="/etc/restic-profile"
    local -a env_files=()
    local -a managed_env_vars=(
        RESTIC_PROFILE_NAME
        RESTIC_PROFILE_RESTIC_BINARY
        RESTIC_REPOSITORY
        RESTIC_PASSWORD
        RESTIC_REST_USERNAME
        RESTIC_REST_PASSWORD
        RESTIC_CACERT
        AWS_DEFAULT_REGION
        AWS_ACCESS_KEY_ID
        AWS_SECRET_ACCESS_KEY
        GOOGLE_PROJECT_ID
        GOOGLE_ACCESS_TOKEN
        GOOGLE_APPLICATION_CREDENTIALS
    )
    local -a profile_names=()
    local env_file profile_name managed_env_var i choice selected_env

    if [[ ! -d "${config_dir}" ]]; then
        printf "Config directory not found: %s\n" "${config_dir}" >&2
        return 1
    fi

    readarray -t env_files < <(
        find "${config_dir}" -maxdepth 1 -type f -name 'restic-profile-*.env' | sort
    )

    if [[ "${#env_files[@]}" -eq 0 ]]; then
        printf "No profiles found in %s\n" "${config_dir}" >&2
        return 1
    fi

    for env_file in "${env_files[@]}"; do
        profile_name="${env_file##*/restic-profile-}"
        profile_name="${profile_name%.env}"
        profile_names+=("${profile_name}")
    done

    for i in "${!profile_names[@]}"; do
        printf "%3d | %s\n" "$((i + 1))" "${profile_names[i]}" >&2
    done

    printf "Select profile [1-%d]: " "${#profile_names[@]}" >&2
    read -r choice

    if [[ ! "${choice}" =~ ^[1-9][0-9]*$ ]] || (( choice < 1 || choice > ${#env_files[@]} )); then
        printf "Invalid selection: %s\n" "${choice}" >&2
        return 1
    fi

    selected_env="${env_files[$((choice - 1))]}"
    for managed_env_var in "${managed_env_vars[@]}"; do
        unset "${managed_env_var}"
    done

    # shellcheck disable=SC1090
    source "${selected_env}"

    printf "Loaded profile: %s\n" "${profile_names[$((choice - 1))]}" >&2
}
