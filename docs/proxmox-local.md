# Deploy Securo on a compact Proxmox VM

This profile runs Securo on one Debian VM with a 16 GiB local virtual disk.
It assumes transaction data only: no attachments, local LLM, embedding model,
NAS mount, or application backup. PostgreSQL remains on the VM's Docker volume.

The VM pulls prebuilt images. It never compiles Securo locally, which avoids
duplicating source trees, package caches, and Docker build layers on the small
disk.

## Resources

- Debian 13 netinst ISO
- 2 vCPU
- 4 GiB RAM
- 16 GiB VirtIO SCSI disk with discard enabled
- VirtIO network adapter
- Reserved DHCP address

Do not enable the agents profile on this VM. A separate deployment with more
RAM and disk is required if attachments, embeddings, or a local LLM are added.

## 1. Create and install the VM

Download the current Debian 13 amd64 netinst ISO from Debian, upload it to the
Proxmox `local` ISO store, and create a VM with the resources above. During the
Debian installer:

1. Use guided partitioning with all files in one partition.
2. Select only **SSH server** and **standard system utilities**.
3. Create the `securo` user.
4. Do not install a desktop environment.

After the first boot:

```bash
sudo apt update
sudo apt full-upgrade -y
sudo apt install -y qemu-guest-agent ca-certificates curl git openssl
sudo systemctl enable --now qemu-guest-agent
```

Enable **QEMU Guest Agent** and **Discard** for the VM in Proxmox.

## 2. Configure SSH

On the computer that will administer Securo, create a dedicated key if needed:

```bash
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/securo_proxmox
ssh-copy-id -i ~/.ssh/securo_proxmox.pub securo@SECURO_VM_IP
ssh -i ~/.ssh/securo_proxmox securo@SECURO_VM_IP
```

Verify that key login works in a second terminal. Then add
`/etc/ssh/sshd_config.d/10-securo.conf` in the VM:

```text
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
```

Validate before reloading:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

Never copy the private key to the VM or this repository.

## 3. Install Docker

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker securo
```

Log out and back in, then verify `docker version` and `docker compose version`.
The Docker group is root-equivalent; only the deployment operator belongs in it.

## 4. Configure Securo

```bash
sudo git clone --branch bessa/main \
  https://github.com/gabrielvcbessa/securo.git /opt/securo
sudo chown -R securo:securo /opt/securo
cd /opt/securo
cp deploy/proxmox/.env.example .env
chmod 600 .env
```

Generate three independent secrets:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Edit `.env` and replace every placeholder. Use the same database password in
`POSTGRES_PASSWORD` and `DATABASE_URL`; use different values for `SECRET_KEY`
and `AGENTS_MCP_JWT_SECRET`. Add the newly rotated Pluggy credentials only to
this file. Never commit `.env`.

If the image packages are private, use a GitHub token with only
`read:packages` to log in:

```bash
printf '%s' 'READ_PACKAGES_TOKEN' | docker login ghcr.io \
  --username gabrielvcbessa --password-stdin
```

Delete the token from shell history after login.

## 5. HTTPS

Point `SECURO_SITE_ADDRESS` and `FRONTEND_URL` at the same HTTPS hostname.
Caddy is the only published application service; backend, PostgreSQL, and
Redis remain private to the Compose network.

For a public DNS name, resolve it to the VM and forward TCP 80 and TCP/UDP 443.
For a LAN-only install, use a trusted internal reverse proxy or Tailscale HTTPS.
Do not use an untrusted Caddy internal CA on Android: the app will reject it
unless its root certificate is installed on every device.

## 6. Deploy an immutable build

Obtain the full `sha-<commit>` image tag from the image build and run:

```bash
cd /opt/securo
chmod +x deploy/proxmox/deploy.sh deploy/proxmox/rollback.sh \
  deploy/proxmox/check-disk.sh
./deploy/proxmox/deploy.sh sha-FULL_40_CHARACTER_COMMIT
```

Open the HTTPS URL, create the first user, and disable open registration if
no other users should sign up.

To roll back to the immediately preceding image tag:

```bash
./deploy/proxmox/rollback.sh
```

The rollback changes containers, not the database schema. Review migrations
before rolling back across a commit that changes the database.

## 7. Disk monitoring and updates

Install the warning-only disk monitor:

```bash
sudo install -m 644 deploy/proxmox/systemd/securo-disk-check.service \
  /etc/systemd/system/
sudo install -m 644 deploy/proxmox/systemd/securo-disk-check.timer \
  /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now securo-disk-check.timer
```

Inspect it with:

```bash
systemctl list-timers securo-disk-check.timer
journalctl -u securo-disk-check.service
```

The Compose stack rotates each container's logs at 3 x 10 MiB. The monitor
warns at 80% usage and never deletes data or images automatically.

For an update:

```bash
cd /opt/securo
git pull --ff-only origin bessa/main
./deploy/proxmox/deploy.sh sha-NEW_FULL_40_CHARACTER_COMMIT
```

Keep the current and previous image tags for rollback. After a successful
update, inspect old images with `docker image ls` and remove only tags you have
explicitly confirmed are no longer rollback targets.
