#!/usr/bin/env bash
set -Eeuo pipefail

readonly CLOUD_IMAGE_URL="https://cloud-images.ubuntu.com/releases/jammy/release-20260826/ubuntu-22.04-server-cloudimg-amd64.img"
readonly CLOUD_IMAGE_SHA256="c0a5af17e6c0f76351fe07e2fffef3011dab1facb8a8ed5701dcf648dabd4f0a"
readonly CURRENT_DOCKER="5:29.7.2-1~ubuntu.22.04~jammy"
readonly CURRENT_CONTAINERD="2.3.3-1~ubuntu.22.04~jammy"
readonly CURRENT_BUILDX="0.36.1-1~ubuntu.22.04~jammy"
readonly CURRENT_COMPOSE="5.5.0-1~ubuntu.22.04~jammy"
readonly CANDIDATE_DOCKER="5:29.6.2-1~ubuntu.22.04~jammy"
readonly CANDIDATE_CONTAINERD="2.2.6-1~ubuntu.22.04~jammy"
readonly CANDIDATE_BUILDX="0.35.0-1~ubuntu.22.04~jammy"
readonly CANDIDATE_COMPOSE="5.3.1-1~ubuntu.22.04~jammy"

task_dir="$(mktemp -d)"
qemu_pid=""
cleanup() {
  if [[ -n "${qemu_pid}" ]] && kill -0 "${qemu_pid}" 2>/dev/null; then
    kill "${qemu_pid}" || true
  fi
}
trap cleanup EXIT

ssh_key="${task_dir}/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -f "${ssh_key}"

curl --fail --location --retry 3 --output "${task_dir}/jammy.img" "${CLOUD_IMAGE_URL}"
printf '%s  %s\n' "${CLOUD_IMAGE_SHA256}" "${task_dir}/jammy.img" | sha256sum --check
qemu-img create -q -f qcow2 -F qcow2 -b "${task_dir}/jammy.img" "${task_dir}/guest.qcow2" 16G

cat >"${task_dir}/user-data" <<EOF
#cloud-config
users:
  - default
  - name: stage6
    groups: [sudo]
    shell: /bin/bash
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - $(<"${ssh_key}.pub")
ssh_pwauth: false
disable_root: true
package_update: false
EOF
cat >"${task_dir}/meta-data" <<'EOF'
instance-id: stage6-seccomp-offhost
local-hostname: stage6-seccomp-offhost
EOF
cloud-localds "${task_dir}/seed.img" "${task_dir}/user-data" "${task_dir}/meta-data"

accel="tcg"
cpu="max"
if [[ -r /dev/kvm && -w /dev/kvm ]]; then
  accel="kvm"
  cpu="host"
fi
qemu-system-x86_64 \
  -daemonize -pidfile "${task_dir}/qemu.pid" \
  -machine "accel=${accel}" -cpu "${cpu}" -m 4096 -smp 2 \
  -drive "file=${task_dir}/guest.qcow2,if=virtio,format=qcow2" \
  -drive "file=${task_dir}/seed.img,if=virtio,format=raw" \
  -device virtio-net-pci,netdev=net0 \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 \
  -display none -serial "file:${task_dir}/serial.log"
qemu_pid="$(<"${task_dir}/qemu.pid")"

ssh_args=(-i "${ssh_key}" -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5)
for _ in $(seq 1 120); do
  if ssh "${ssh_args[@]}" stage6@127.0.0.1 true 2>/dev/null; then
    break
  fi
  sleep 2
done
ssh "${ssh_args[@]}" stage6@127.0.0.1 'cloud-init status --wait'

remote() {
  ssh "${ssh_args[@]}" stage6@127.0.0.1 "$@"
}

remote 'set -Eeuo pipefail; . /etc/os-release; test "$VERSION_ID" = 22.04; case "$(uname -r)" in 5.15.*) ;; *) echo "OFFHOST_ERROR=kernel_not_5.15" >&2; exit 1;; esac'
remote 'sudo install -m 0755 -d /etc/apt/keyrings; curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null; sudo chmod a+r /etc/apt/keyrings/docker.asc; echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu jammy stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null; sudo apt-get update -qq'

install_tuple() {
  local docker_version="$1" containerd_version="$2" buildx_version="$3" compose_version="$4"
  remote "sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --allow-downgrades docker-ce='${docker_version}' docker-ce-cli='${docker_version}' docker-ce-rootless-extras='${docker_version}' containerd.io='${containerd_version}' docker-buildx-plugin='${buildx_version}' docker-compose-plugin='${compose_version}'"
}

install_tuple "${CURRENT_DOCKER}" "${CURRENT_CONTAINERD}" "${CURRENT_BUILDX}" "${CURRENT_COMPOSE}"
remote 'printf "OFFHOST_KERNEL=%s\n" "$(uname -r)"; printf "OFFHOST_LIBSECCOMP=%s\n" "$(dpkg-query -W -f='"'"'${Version}'"'"' libseccomp2)"; sudo docker version --format "OFFHOST_DOCKER={{.Server.Version}}"; containerd --version | sed "s/^/OFFHOST_CONTAINERD=/"; sudo runc --version | head -n 1 | sed "s/^/OFFHOST_RUNC=/"; printf "OFFHOST_LSM="; cat /sys/kernel/security/lsm 2>/dev/null || true; printf "OFFHOST_SECCOMP_ACTIONS="; cat /proc/sys/kernel/seccomp/actions_avail'
remote 'sudo docker run --detach --name seccomp-probe alpine:3.22.1 sleep infinity >/dev/null'

set +e
current_output="$(remote 'sudo docker exec seccomp-probe true' 2>&1)"
current_status=$?
set -e
if (( current_status == 0 )); then
  printf '%s\n' 'DEFAULT_PROFILE_EXEC=PASS'
  remote 'sudo docker run --detach --name seccomp-hardened --security-opt no-new-privileges:true --cap-drop ALL --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m alpine:3.22.1 sleep infinity >/dev/null'
  set +e
  current_output="$(remote 'sudo docker exec seccomp-hardened true' 2>&1)"
  current_status=$?
  set -e
  if (( current_status == 0 )); then
    printf '%s\n' 'HARDENED_PROFILE_EXEC=PASS' 'SECCOMP_REPRODUCED_OFFHOST=NO' 'FIX_PROVEN_OFFHOST=NO'
    exit 2
  fi
fi
if [[ "${current_output}" != *"unable to init seccomp"* || "${current_output}" != *"errno 524"* ]]; then
  printf '%s\n' 'SECCOMP_REPRODUCED_OFFHOST=NO' 'FIX_PROVEN_OFFHOST=NO'
  printf 'CURRENT_TUPLE_UNEXPECTED_FAILURE=%q\n' "${current_output}"
  exit 3
fi
printf '%s\n' 'SECCOMP_REPRODUCED_OFFHOST=YES'

install_tuple "${CANDIDATE_DOCKER}" "${CANDIDATE_CONTAINERD}" "${CANDIDATE_BUILDX}" "${CANDIDATE_COMPOSE}"
remote 'sudo systemctl is-active --quiet docker; sudo docker start seccomp-probe >/dev/null || true; sudo docker start seccomp-hardened >/dev/null || true'
if ! remote 'sudo docker exec seccomp-probe true; if sudo docker inspect seccomp-hardened >/dev/null 2>&1; then sudo docker exec seccomp-hardened true; fi'; then
  printf '%s\n' 'FIX_PROVEN_OFFHOST=NO'
  exit 4
fi

remote 'printf "OFFHOST_KERNEL=%s\n" "$(uname -r)"; sudo docker version --format "OFFHOST_DOCKER={{.Server.Version}}"; containerd --version | sed "s/^/OFFHOST_CONTAINERD=/"; sudo runc --version | head -n 1 | sed "s/^/OFFHOST_RUNC=/"'
printf '%s\n' 'FIX_PROVEN_OFFHOST=YES' 'SECCOMP_DISABLED=NO' 'REAL_HOST_MUTATION=NO' 'PRODUCTION_CHANGED=NO'
