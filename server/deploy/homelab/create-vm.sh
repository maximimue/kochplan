#!/usr/bin/env bash
# Auf dem PROXMOX-HOST als root ausführen. Legt eine Debian-13-Cloud-Image-VM an.
# Alle Werte per Umgebungsvariable überschreibbar, z. B.:
#   VMID=210 STORAGE=local-zfs BRIDGE=vmbr0 VLAN=20 IP=192.168.178.60/24 GW=192.168.178.1 \
#   SSH_KEY=/root/max.pub bash create-vm.sh
set -euo pipefail

VMID=${VMID:-210}
NAME=${NAME:-kochplan}
STORAGE=${STORAGE:-local-lvm}
BRIDGE=${BRIDGE:-vmbr0}
VLAN=${VLAN:-}
CORES=${CORES:-2}
MEM=${MEM:-4096}
DISK=${DISK:-32G}
CIUSER=${CIUSER:-kochplan}
SSH_KEY=${SSH_KEY:-/root/.ssh/authorized_keys}
IP=${IP:-dhcp}              # oder 192.168.x.y/24 (dann GW setzen)
GW=${GW:-}
NAMESERVER=${NAMESERVER:-}  # z. B. IP des Pi-hole

IMG=debian-13-genericcloud-amd64.qcow2
BASE=https://cloud.debian.org/images/cloud/trixie/latest
CACHE=/var/lib/vz/template/cache

qm status "$VMID" &>/dev/null && { echo "VMID $VMID existiert bereits"; exit 1; }
[ -f "$SSH_KEY" ] || { echo "SSH-Key $SSH_KEY nicht gefunden"; exit 1; }

mkdir -p "$CACHE" && cd "$CACHE"
wget -q -N "$BASE/$IMG" "$BASE/SHA512SUMS"
grep " $IMG\$" SHA512SUMS | sha512sum -c -

NET="virtio,bridge=$BRIDGE,firewall=1${VLAN:+,tag=$VLAN}"
IPCFG="ip=$IP${GW:+,gw=$GW}"

qm create "$VMID" --name "$NAME" --ostype l26 \
  --cpu host --cores "$CORES" --memory "$MEM" --balloon 0 \
  --scsihw virtio-scsi-single --net0 "$NET" \
  --agent enabled=1,fstrim_cloned_disks=1 --serial0 socket --vga serial0 \
  --onboot 1 --tags "kochplan;docker"
qm set "$VMID" --scsi0 "$STORAGE:0,import-from=$CACHE/$IMG,discard=on,ssd=1,iothread=1"
qm disk resize "$VMID" scsi0 "$DISK"
qm set "$VMID" --ide2 "$STORAGE:cloudinit" --boot order=scsi0
qm set "$VMID" --ciuser "$CIUSER" --sshkeys "$SSH_KEY" --ipconfig0 "$IPCFG" ${NAMESERVER:+--nameserver "$NAMESERVER"}
qm start "$VMID"

echo "VM $VMID ($NAME) gestartet. Nach ~1 Min: ssh $CIUSER@<IP>"
echo "Dann: git clone <repo> kochplan && sudo bash kochplan/server/deploy/homelab/bootstrap-debian.sh"
