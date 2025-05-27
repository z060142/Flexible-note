import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, func # Added func

from models import db, QueryRelation, Tag, Segment, Session, session_tags, segment_tags
from config import CATEGORY_COLORS

# Initialize logger
logger = logging.getLogger(__name__)

# Create Blueprint
relation_bp = Blueprint('relation', __name__)

# Copied build_relation_graph function and its helpers
def build_relation_graph(start_point, depth=2):
    """構建關聯圖譜數據"""
    try:
        nodes = {}  # 存儲節點，避免重複
        links = []  # 存儲連接
        visited = set()  # 已處理的節點
        
        # 查找起始點
        start_tag = Tag.query.filter(
            or_(Tag.name.contains(start_point), Tag.name == start_point)
        ).first()
        
        if not start_tag:
            start_segments = Segment.query.filter(
                or_(Segment.title.contains(start_point), Segment.content.contains(start_point))
            ).limit(5).all()
            
            if not start_segments:
                return {'nodes': [], 'links': [], 'message': f'找不到與 "{start_point}" 相關的內容'}
            
            start_tags_list = [] # Renamed to avoid conflict
            for segment in start_segments:
                start_tags_list.extend(segment.tags)
            
            if not start_tags_list:
                return {'nodes': [], 'links': [], 'message': f'找到內容但沒有相關標籤'}
                
            start_tag = start_tags_list[0]
        
        # Helper: Add node to graph
        def add_node(tag, node_type='tag', level=0):
            node_id = f"{node_type}_{tag.id}"
            if node_id not in nodes:
                nodes[node_id] = {
                    'id': node_id, 'name': tag.name, 'category': tag.category,
                    'color': tag.color or CATEGORY_COLORS.get(tag.category, '#6c757d'),
                    'type': node_type, 'level': level, 'size': 10 + level * 5
                }
            return node_id
        
        # Helper: Add link to graph
        def add_link(source_id, target_id, relation_type, strength=1.0):
            link_id = f"{source_id}_{target_id}"
            reverse_link_id = f"{target_id}_{source_id}"
            if not any(l['id'] == link_id or l['id'] == reverse_link_id for l in links):
                links.append({
                    'id': link_id, 'source': source_id, 'target': target_id,
                    'relation_type': relation_type, 'strength': strength,
                    'value': strength * 10
                })
        
        # Helper: Find related tags by pattern
        def find_tags_by_pattern(source_tag, target_category):
            segments = Segment.query.join(Segment.tags).filter(Tag.id == source_tag.id).all()
            found_tags_list = [] # Renamed
            for segment in segments:
                for tag_item in segment.tags: # Renamed
                    if tag_item.category == target_category and tag_item not in found_tags_list:
                        found_tags_list.append(tag_item)
            return found_tags_list[:5]

        # Helper: Get relation type between two tags
        def get_relation_type(tag1, tag2):
            if tag1.category == '症狀' and tag2.category == '病因': return 'symptom_to_cause'
            elif tag1.category == '病因' and tag2.category == '手法': return 'cause_to_treatment'
            elif tag1.category == '手法' and tag2.category == '位置': return 'method_to_location'
            elif tag1.category == tag2.category: return 'same_category'
            else: return 'co_occurrence'

        # Helper: Find all related tags for a given tag
        def find_related_tags(tag_param): # Renamed tag to tag_param
            related_tags_map = {} # Renamed
            segments_with_tag = Segment.query.join(Segment.tags).filter(Tag.id == tag_param.id).all()
            for segment in segments_with_tag:
                for other_tag in segment.tags:
                    if other_tag.id != tag_param.id:
                        if other_tag not in related_tags_map:
                            related_tags_map[other_tag] = {'type': get_relation_type(tag_param, other_tag), 'strength': 0.1, 'co_occurrence': 0}
                        related_tags_map[other_tag]['co_occurrence'] += 1
                        related_tags_map[other_tag]['strength'] += 0.1
            
            sessions_with_tag = Session.query.join(Session.tags).filter(Tag.id == tag_param.id).all()
            for session_item in sessions_with_tag: # Renamed
                for other_tag in session_item.tags:
                    if other_tag.id != tag_param.id:
                        if other_tag not in related_tags_map:
                            related_tags_map[other_tag] = {'type': get_relation_type(tag_param, other_tag), 'strength': 0.05, 'co_occurrence': 0}
                        related_tags_map[other_tag]['strength'] += 0.05
            
            same_category_tags = Tag.query.filter(Tag.category == tag_param.category, Tag.id != tag_param.id).limit(3).all()
            for other_tag in same_category_tags:
                if other_tag not in related_tags_map:
                    related_tags_map[other_tag] = {'type': 'same_category', 'strength': 0.3, 'co_occurrence': 0}

            if tag_param.category == '症狀':
                cause_tags_list = find_tags_by_pattern(tag_param, '病因') # Renamed
                for cause_tag in cause_tags_list:
                    related_tags_map[cause_tag] = {'type': 'symptom_to_cause', 'strength': 0.8, 'co_occurrence': 0}
            elif tag_param.category == '病因':
                treatment_tags_list = find_tags_by_pattern(tag_param, '手法') # Renamed
                for treatment_tag in treatment_tags_list:
                    related_tags_map[treatment_tag] = {'type': 'cause_to_treatment', 'strength': 0.7, 'co_occurrence': 0}
            return related_tags_map

        # Main exploration logic for build_relation_graph
        def explore_relations(tag_param, current_depth, max_depth): # Renamed tag to tag_param
            if current_depth > max_depth or tag_param.id in visited: return
            visited.add(tag_param.id)
            current_node_id = add_node(tag_param, 'tag', current_depth)
            
            related_tags_data = find_related_tags(tag_param) # Renamed
            for related_tag_item, relation_info in related_tags_data.items(): # Renamed
                if related_tag_item.id != tag_param.id:
                    related_node_id = add_node(related_tag_item, 'tag', current_depth + 1)
                    add_link(current_node_id, related_node_id, relation_info['type'], relation_info['strength'])
                    if current_depth < max_depth:
                        explore_relations(related_tag_item, current_depth + 1, max_depth)
        
        explore_relations(start_tag, 0, depth)
        
        nodes_list = list(nodes.values())
        for node in nodes_list:
            connections = len([link for link in links if link['source'] == node['id'] or link['target'] == node['id']])
            node['importance'] = connections
            node['size'] = max(10, min(30, 10 + connections * 2))
        
        return {'nodes': nodes_list, 'links': links, 'center_node': f"tag_{start_tag.id}", 
                'total_nodes': len(nodes_list), 'total_links': len(links), 'max_depth': depth}
    except Exception as e:
        logger.error(f"構建關聯圖失敗: {e}")
        return {'nodes': [], 'links': [], 'error': str(e)}

# Moved Flask Route
@relation_bp.route('/api/relation', methods=['POST'])
def create_relation():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        relation = QueryRelation(
            relation_type=data.get('relation_type'),
            source_type=data.get('source_type'),
            source_id=data.get('source_id'),
            target_type=data.get('target_type'),
            target_id=data.get('target_id'),
            strength=data.get('strength', 1.0),
            notes=data.get('notes', '')
        )
        db.session.add(relation)
        db.session.commit()
        return jsonify({'success': True, 'relation_id': relation.id})
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating relation: {str(e)}") # Added logger
        return jsonify({'error': str(e)}), 500
