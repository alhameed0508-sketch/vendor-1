#!/bin/bash
# Neo4j database backup script
# Schedule via cron: 0 1 * * * /path/to/neo4j_backup.sh
#
# Performs a timestamped dump of the Neo4j database, compresses it,
# and retains 7 days of backups.

set -e

BACKUP_DIR="${BACKUP_DIR:-/backups/neo4j}"
NEO4J_CONTAINER="${NEO4J_CONTAINER:-mulecatch_neo4j}"
RETENTION_DAYS=7

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/neo4j_backup_${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting Neo4j backup..."

# Create dump using neo4j-admin
docker exec "$NEO4J_CONTAINER" neo4j-admin database dump neo4j --to-path=/tmp/

# Copy dump from container
docker cp "$NEO4J_CONTAINER:/tmp/neo4j.dump" "$BACKUP_FILE"

# Compress
gzip "$BACKUP_FILE"
echo "[$(date)] Backup created: ${BACKUP_FILE}.gz"

# Cleanup: remove backups older than retention period
find "$BACKUP_DIR" -name "neo4j_backup_*.dump.gz" -mtime +$RETENTION_DAYS -delete
echo "[$(date)] Cleaned up backups older than $RETENTION_DAYS days"

echo "[$(date)] Backup complete."
