# Arch Linux test VM on macOS

Use the official Arch Linux x86_64 cloud image with QEMU, not the legacy
`Vagrantfile`. QEMU can emulate x86_64 on Apple Silicon with TCG; package
installation and tests will be slower than native virtualization. VirtualBox on
Apple Silicon does not run x86 guests. This procedure does not require an Arch
Linux ARM image or a Vagrant box.

The guest gets a disposable disk, a new SSH key, and a localhost-only SSH port.
There are no shared host directories, forwarded SSH agents, or copied personal
keys. Only the repository's guarded, files-only provisioning is supported;
package upgrades, reboots during provisioning, and legacy VM cleanup remain
outside that path. User-mode networking still permits outbound connections and
access to host services; the guest is not network-isolated. Stop sensitive
local services before booting an untrusted guest.

## Prepare the image

Install QEMU (`brew install qemu`) if it is not already available. Run these
commands from the repository root. Keep the printed workspace path for the
second terminal used below.

```sh
vm_dir="$(mktemp -d "$HOME/dotfiles-arch-vm.XXXXXX")"
printf '%s\n' "$vm_dir"
mirror=https://geo.mirror.pkgbuild.com/images/latest
image=Arch-Linux-x86_64-cloudimg.qcow2
curl --fail --location --proto '=https' -o "$vm_dir/$image" "$mirror/$image"
curl --fail --location --proto '=https' -o "$vm_dir/$image.SHA256" "$mirror/$image.SHA256"
(cd "$vm_dir" && shasum -a 256 -c "$image.SHA256")
```

Stop if checksum verification fails. The `latest` image can change between the
two downloads; fetch a matching pair rather than bypassing verification. The
[official image listing](https://geo.mirror.pkgbuild.com/images/latest/) also
provides versioned filenames and signatures. A checksum from the same mirror
detects corruption but does not authenticate the image independently of that
mirror. For signature verification, use a trusted Arch signing key.

Create an overlay so the downloaded image remains unchanged:

```sh
qemu-img create -f qcow2 -F qcow2 -b "$vm_dir/$image" "$vm_dir/disk.qcow2" 12G
ssh-keygen -q -t ed25519 -N '' -f "$vm_dir/id_ed25519" -C dotfiles-arch-test
mkdir "$vm_dir/seed"
python3 - "$vm_dir" <<'PY'
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
key = json.dumps(root.joinpath("id_ed25519.pub").read_text().strip())
root.joinpath("seed/user-data").write_text(f"""#cloud-config
hostname: dotfiles-arch-test
users:
  - name: arch
    groups: [wheel]
    sudo: ['ALL=(ALL) NOPASSWD:ALL']
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys: [{key}]
ssh_pwauth: false
disable_root: true
package_update: false
package_upgrade: false
""")
root.joinpath("seed/meta-data").write_text(
    "instance-id: dotfiles-arch-test\nlocal-hostname: dotfiles-arch-test\n"
)
PY
hdiutil makehybrid -o "$vm_dir/seed.iso" "$vm_dir/seed" -iso -joliet -default-volume-name cidata
```

## Boot and connect

Run QEMU in the foreground in this terminal. Port 22220 must be free; choose
another port in both QEMU and the SSH commands if it is already in use.

```sh
qemu-system-x86_64 \
  -name dotfiles-arch-test -machine q35 -accel tcg,thread=multi -cpu max \
  -m 3072 -smp 2 \
  -drive "file=$vm_dir/disk.qcow2,if=virtio,format=qcow2" \
  -drive "file=$vm_dir/seed.iso,if=virtio,format=raw,readonly=on" \
  -netdev user,id=net0,hostfwd=tcp:127.0.0.1:22220-:22 \
  -device virtio-net-pci,netdev=net0 \
  -display none -serial "file:$vm_dir/serial.log" -monitor none -no-reboot
```

In a second terminal, set `vm_dir` to the path printed earlier. Define an SSH
helper that ignores your normal SSH configuration and uses only the test key:

```sh
arch_ssh() {
  ssh -F /dev/null -p 22220 -i "$vm_dir/id_ed25519" \
    -o IdentitiesOnly=yes -o IdentityAgent=none -o ForwardAgent=no \
    -o BatchMode=yes -o ConnectTimeout=10 \
    -o "UserKnownHostsFile=$vm_dir/known_hosts" \
    -o GlobalKnownHostsFile=/dev/null -o StrictHostKeyChecking=accept-new \
    arch@127.0.0.1 "$@"
}
arch_ssh 'uname -sm; python3 --version; sudo -n cloud-init status --wait --long'
```

Allow time for the first boot before retrying SSH. Check `serial.log` if it
never becomes available. Successful cloud-init should report `status: done`
without errors. The new host key is trusted only within this private test
workspace.

## Test dotfiles provisioning

Copy the committed repository without `.git`, local secrets, or the host's
Python environment. This uses `HEAD`, not uncommitted edits:

```sh
git archive --format=tar HEAD | arch_ssh 'mkdir -p ~/dotfiles && tar -xf - -C ~/dotfiles'
arch_ssh
```

Inside the guest, make the Python version in `.python-version` available on
PATH before bootstrapping. The cloud image's system Python may differ. Install
the pinned version under the guest user's home with mise or a verified
[standalone Python build](https://github.com/astral-sh/python-build-standalone),
without replacing `/usr/bin/python3`. See [Python environment setup](development.md)
and the [interpreter upgrade notes](dependency-upgrades.md#scope-and-compatibility)
if an older `.venv` already exists.

Run the normal launcher inside the guest, not a direct Ansible command from
macOS. `dotfiles_home` isolates destinations from the guest's own shell files.
Under software emulation, allow several minutes per command: an apply runs a
full preview first, then the same tasks again. Do not skip that preview to make
the VM run faster.

```sh
cd ~/dotfiles
./runAnsible.sh --help
.venv/bin/python3 --version
./runAnsible.sh --check --diff -e "dotfiles_home=$HOME/dotfiles-test-home"
./runAnsible.sh --diff -e "dotfiles_home=$HOME/dotfiles-test-home"
./runAnsible.sh --check --diff -e "dotfiles_home=$HOME/dotfiles-test-home"
```

The first preview must not create the destination. The apply repeats the audit
and preview before creating links. The final preview should propose no changes.
Check representative links such as `.bashrc`, `.xinitrc`, and
`.config/Code/User/settings.json` under `dotfiles-test-home`.

Also test a separate destination containing an existing `.xinitrc` file or a
symlink to a different source. The launcher must refuse to overwrite or retarget
it and must not apply the other changes. Do not resolve these deliberately
created test conflicts by weakening the guard.

## Shut down and remove the VM

Exit the guest shell, then shut down from the host's second terminal:

```sh
arch_ssh 'sudo -n poweroff'
```

If SSH shutdown fails, press Ctrl-C in the QEMU terminal. This is an unclean
stop of the disposable guest, so preserve its logs before discarding the disk.
Agents use the tracked process shutdown described in `AGENTS.md` instead.

Wait for QEMU to exit in its terminal. Preserve any logs you need, then remove
only the printed VM workspace, including its disks and disposable SSH key.
Do not delete a disk while QEMU is still using it.

See [Arch provisioning limits](provisioning.md#arch-linux-and-vagrant) for the
legacy system and Vagrant paths that remain blocked.
