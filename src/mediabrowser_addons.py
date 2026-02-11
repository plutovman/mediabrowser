def get_file_status(file_id):
    """Check if file exists in proj, arch, or both tables"""
    conn = db_get_connection()
    
    # Single query across both tables
    query = '''
        SELECT 
            (SELECT 1 FROM media_proj WHERE file_id = ?) as in_proj,
            (SELECT 1 FROM media_arch WHERE file_id = ?) as in_arch
    '''
    result = conn.execute(query, (file_id, file_id)).fetchone()
    conn.close()
    
    return {
        'in_proj': bool(result['in_proj']),
        'in_arch': bool(result['in_arch']),
        'in_both': bool(result['in_proj'] and result['in_arch'])
    }

# Could also use JOINs to find curated items:
def get_curated_items():
    """Get items that exist in both tables"""
    conn = db_get_connection()
    
    query = '''
        SELECT p.* 
        FROM media_proj p
        INNER JOIN media_arch a ON p.file_id = a.file_id
        WHERE p.subject != a.subject  -- Find items with different metadata
    '''
    
    results = conn.execute(query).fetchall()
    conn.close()
    return results


##########

@app.route('/api/archive/copy_from_proj', methods=['POST'])
def api_archive_copy_from_proj():
    """Copy item from media_proj to media_arch (with single DB, uses simple INSERT)"""
    
    try:
        file_id = request.json.get('file_id')
        
        conn = db_get_connection()
        
        # Check if already in archive
        exists = conn.execute(
            'SELECT 1 FROM media_arch WHERE file_id = ?', 
            (file_id,)
        ).fetchone()
        
        if exists:
            conn.close()
            return jsonify({'success': False, 'error': 'Already in archive'})
        
        # Copy from proj to arch in single transaction
        conn.execute('''
            INSERT INTO media_arch 
            SELECT * FROM media_proj WHERE file_id = ?
        ''', (file_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# With separate DBs, this would require:
# 1. SELECT from proj DB
# 2. INSERT to arch DB (separate connection)
# 3. No atomic guarantee between steps

###########


def sync_metadata_across_tables(file_id, field, value, source_table):
    """
    Update metadata field in source table and sync to other table if file_id exists there.
    
    Args:
        file_id: Unique file identifier
        field: Column name to update
        value: New value
        source_table: Table where edit originated (media_proj or media_arch)
    
    Returns:
        dict with sync status
    """
    if source_table not in list_db_tables:
        return {'success': False, 'error': 'Invalid source table'}
    
    target_table = db_table_arch if source_table == db_table_proj else db_table_proj
    
    conn = db_get_connection()
    
    try:
        # Update source table
        conn.execute(
            f'UPDATE {source_table} SET {field} = ? WHERE file_id = ?',
            (value, file_id)
        )
        
        # Check if file exists in target table
        exists = conn.execute(
            f'SELECT 1 FROM {target_table} WHERE file_id = ? LIMIT 1',
            (file_id,)
        ).fetchone()
        
        synced = False
        if exists:
            # Sync to target table
            conn.execute(
                f'UPDATE {target_table} SET {field} = ? WHERE file_id = ?',
                (value, file_id)
            )
            synced = True
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'synced': synced,
            'source': source_table,
            'target': target_table if synced else None
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        return {'success': False, 'error': str(e)}

# Update the existing route to use sync function:
@app.route('/update_cart_items', methods=['POST'])
def cart_items_update():
    """Update metadata fields for cart items with automatic sync"""
    
    data = request.get_json()
    db_table = data.get('db_table', list_db_tables[0])
    changes = data.get('changes', [])
    provided_password = data.get('password', '')
    
    # ...existing password validation...
    
    list_columns_editable = ['subject', 'genre', 'setting', 'captions', 'tags', 'lighting', 'category']
    
    results = []
    for change in changes:
        file_id = change.get('file_id')
        field = change.get('field')
        value = change.get('value', '')
        
        if field not in list_columns_editable:
            continue
        
        # Use sync function for each change
        result = sync_metadata_across_tables(file_id, field, value, db_table)
        results.append(result)
    
    success_count = sum(1 for r in results if r.get('success'))
    sync_count = sum(1 for r in results if r.get('synced'))
    
    return jsonify({
        'success': True,
        'updated': success_count,
        'synced': sync_count,
        'details': results
    })


##########
def enrich_media_paths(item):
    """Enrich media item with absolute/relative paths and sync status"""
    
    item_dict = dict(item)
    
    # ...existing path enrichment code...
    
    # Check if item exists in other table (for sync indicator)
    file_id = item_dict['file_id']
    current_table = 'unknown'  # You'd pass this as parameter
    
    conn = db_get_connection()
    
    # Determine which table this item came from (context-dependent)
    # Then check if it exists in the other table
    other_table = db_table_arch if current_table == db_table_proj else db_table_proj
    
    exists_in_other = conn.execute(
        f'SELECT 1 FROM {other_table} WHERE file_id = ? LIMIT 1',
        (file_id,)
    ).fetchone()
    
    conn.close()
    
    item_dict['is_synced'] = bool(exists_in_other)
    item_dict['sync_indicator'] = '🔗' if exists_in_other else ''
    
    return item_dict

