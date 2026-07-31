# Deploy Securo on Proxmox with TrueNAS backups

This deployment runs the official Securo containers inside a Debian virtual
machine. PostgreSQL and application files stay on the VM's local virtual disk.
A dedicated TrueNAS dataset receives daily logical database and file backups.

Keeping the live database local avoids making Securo's availability and
database writes depend on the NAS and network. Do not place the PostgreSQL
Docker volume directly on an SMB share. NFS can support PostgreSQL only with
carefully verified durability and mount semantics; it adds no practical
benefit for a single Securo instance.

## Recommended resources

Base deployment without a local LLM:

- Debian 12 VM with UEFI or SeaBIOS
- 2 vCPU
- 4 GiB RAM
- 32 GiB local virtual disk, preferably 64 GiB when storing attachments
- VirtIO SCSI disk and VirtIO network adapter
- A reserved DHCP lease or static IP
- 20-50 GiB TrueNAS backup dataset, adjusted for attachment volume

Use 4 vCPU and 8 GiB RAM when enabling agents with native embeddings. Run
Ollama separately and size it for the selected model; it can require
substantially more RAM or a passed-through GPU.

## 1. Create the TrueNAS dataset and NFS share

In TrueNAS:

1. Open **Datasets**, select the storage pool, and create a child dataset named
   `securo-backups`. Do not share the pool's root dataset.
2. Use the **Generic** preset and keep **Sync** set to `Standard` or `Always`.
3. Enable dataset encryption when the pool is not already encrypted.
4. Set a quota appropriate for the retention policy, initially 50 GiB.
5. Create an NFS share for `/mnt/<pool>/securo-backups`.
6. Restrict **Allowed Hosts** to the Securo VM's reserved IP.
7. Enable the NFS service.
8. Configure periodic ZFS snapshots after the first successful backup. A
   practical starting point is seven daily and four weekly snapshots.

The backup contains personal financial data. Keep NFS on a trusted LAN or
storage VLAN and do not expose it through the internet.

## 2. Create the Proxmox VM

Create a Debian 12 VM in the Proxmox UI:

1. Assign 2 CPU cores, 4 GiB RAM, and a 32-64 GiB disk.
2. Use a VirtIO network interface attached to the trusted LAN bridge.
3. Install Debian with only **SSH server** and **standard system utilities**.
4. Reserve the VM's IP in DHCP.
5. Install the QEMU guest agent:

   ```bash
   sudo apt update
   sudo apt install -y qemu-guest-agent
   sudo systemctl enable --now qemu-guest-agent
   ```

Enable **QEMU Guest Agent** in the VM's Proxmox options after installation.

## 3. Create an SSH deployment account

On the VM, create a non-root operator:

```bash
sudo adduser securo
sudo usermod -aG sudo securo
sudo install -d -m 700 -o securo -g securo /home/securo/.ssh
sudo install -m 600 -o securo -g securo /dev/null /home/securo/.ssh/authorized_keys
```

Append the operator's SSH public key to
`/home/securo/.ssh/authorized_keys`. Verify key login in a second terminal
before changing SSH policy.

After key login works, create `/etc/ssh/sshd_config.d/10-securo.conf`:

```text
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
```

Validate and reload SSH:

```bash
sudo sshd -t
sudo systemctl reload ssh
```

Do not copy a private SSH key to the VM or commit one to this repository.

## 4. Install Docker and mount TrueNAS

Install Docker Engine and the Compose plugin from Docker's official Debian
repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world
```

Then allow the deployment account to operate Docker:

```bash
sudo usermod -aG docker securo
```

Logging out and back in applies the new group. Membership in the `docker`
group is effectively root access; grant it only to deployment operators.

Install the NFS client and mount the backup dataset:

```bash
sudo apt install -y nfs-common
sudo mkdir -p /mnt/securo-backups
sudo mount -t nfs -o nfsvers=4.2,hard,timeo=600,retrans=2 \
  <TRUENAS_IP>:/mnt/<pool>/securo-backups /mnt/securo-backups
```

Confirm the VM can create and remove a test file. Then add this entry to
`/etc/fstab`:

```fstab
<TRUENAS_IP>:/mnt/<pool>/securo-backups /mnt/securo-backups nfs4 rw,hard,nofail,_netdev,x-systemd.automount,timeo=600,retrans=2 0 0
```

Run `sudo mount -a` and `mountpoint /mnt/securo-backups` to validate it.

## 5. Start Securo

Clone the repository at `/opt/securo` and make the deployment operator its
owner:

```bash
sudo git clone https://github.com/securo-finance/securo.git /opt/securo
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

Edit `.env` and set:

- `FRONTEND_URL` and `SECURO_SITE_ADDRESS` to the Securo HTTPS hostname
- the same generated database password in `POSTGRES_PASSWORD` and
  `DATABASE_URL`
- independent values for `SECRET_KEY` and `AGENTS_MCP_JWT_SECRET`
- any optional bank provider credentials and callback URL

The hostname must resolve to the VM. For a publicly resolvable hostname, allow
inbound TCP 80 and TCP/UDP 443 so Caddy can obtain and renew a certificate.
For private-only access, put Securo behind an existing internal reverse proxy
or VPN with trusted HTTPS. Do not forward the backend or PostgreSQL ports.

Pull and start the stack:

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  pull

docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  up -d

docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  ps
```

Open the configured HTTPS URL, create the first account, and disable open
registration from the admin settings when no additional users are expected.

## 6. Enable daily backups

Install the supplied systemd units:

```bash
sudo install -m 755 deploy/proxmox/backup.sh /opt/securo/deploy/proxmox/backup.sh
sudo install -m 644 deploy/proxmox/systemd/securo-backup.service /etc/systemd/system/
sudo install -m 644 deploy/proxmox/systemd/securo-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now securo-backup.timer
sudo systemctl start securo-backup.service
sudo systemctl status securo-backup.service
```

Each successful backup creates an immutable-by-convention timestamped
directory containing:

- `database.dump`: PostgreSQL custom-format logical backup
- `files.tar.gz`: transaction attachments and agent knowledge uploads
- `SHA256SUMS`: integrity checksums

The script refuses to run when `/mnt/securo-backups` is not a mounted
filesystem, preventing a NAS outage from silently filling the VM's root disk.

Test restoration into a disposable Securo VM before considering the backup
strategy complete. Proxmox VM backups are useful as a second recovery layer,
but they do not replace the application-aware PostgreSQL dump.

### Restore drill

Never test restoration against the only production instance. Create a
disposable VM, deploy the same Securo version, and copy one timestamped backup
directory to it.

Verify the backup before restoring:

```bash
cd <BACKUP_DIRECTORY>
sha256sum --check SHA256SUMS
docker compose -f /opt/securo/docker-compose.prod.yml exec -T db \
  pg_restore --list < database.dump > /dev/null
tar -tzf files.tar.gz > /dev/null
```

Stop the application services, restore the database into an empty `securo`
database, then extract `files.tar.gz` into the `attachments` and
`agent_knowledge` volumes. Start the application and verify login, accounts,
transactions, reports, attachments, and one bank synchronization. Record the
date of the successful drill.

## Updates

Before updating, run and verify a backup. Then:

```bash
cd /opt/securo
git pull --ff-only
docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  pull
docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  up -d
docker compose \
  -f docker-compose.prod.yml \
  -f deploy/proxmox/compose.caddy.yml \
  ps
```

Database migrations run automatically when the backend starts.
