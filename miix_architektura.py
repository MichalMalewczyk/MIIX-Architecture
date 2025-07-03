bl_info = {
    "name": "MIIX Architektura",
    "blender": (4, 3, 0),
    "category": "Object",
}

import bpy, bmesh, os, re, unicodedata, datetime, math, threading, json, hashlib
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
from bpy.props import EnumProperty, IntProperty, StringProperty, FloatProperty, BoolProperty, CollectionProperty, PointerProperty, FloatVectorProperty
from bpy.types import Panel, Operator
from bpy.app.handlers import persistent

try:
    import ezdxf
except ImportError:
    ezdxf = None


# Predefiniowane kolory Proneko (RGB 0-255)
PRONEKO_COLORS = [
    ('BLACK', 'Czarny', 'Czarny (0,0,0)', (0, 0, 0)),
    ('GRAY1', 'Szary 1', 'Szary 1 (153,153,153)', (153, 153, 153)),
    ('GRAY2', 'Szary 2', 'Szary 2 (190,192,186)', (190, 192, 186)),
    ('GRAY3', 'Szary 3', 'Szary 3 (204,204,204)', (204, 204, 204)),
    ('WHITE', 'Biały', 'Biały (255,255,255)', (255, 255, 255)),
    ('RED1', 'Czerwony 1', 'Czerwony 1 (206,22,22)', (206, 22, 22)),
    ('BROWN1', 'Brązowy 1', 'Brązowy 1 (142,71,35)', (142, 71, 35)),
    ('ORANGE1', 'Pomarańczowy 1', 'Pomarańczowy 1 (206,145,22)', (206, 145, 22)),
    ('GREEN1', 'Zielony 1', 'Zielony 1 (46,139,15)', (46, 139, 15)),
    ('GREEN2', 'Zielony 2', 'Zielony 2 (161,209,71)', (161, 209, 71)),
    ('GREEN3', 'Zielony 3', 'Zielony 3 (203,229,152)', (203, 229, 152)),
    ('BLUE1', 'Niebieski 1', 'Niebieski 1 (25,75,229)', (25, 75, 229)),
    ('BLUE2', 'Niebieski 2', 'Niebieski 2 (132,173,224)', (132,173,224)),
    ('PURPLE1', 'Fioletowy 1', 'Fioletowy 1 (183,20,129)', (183, 20, 129)),
    ('PRONEKO1', 'Proneko 1', 'Proneko 1 (1,22,64)', (1, 22, 64)),
    ('PRONEKO2', 'Proneko 2', 'Proneko 2 (255,235,190)', (255, 235, 190)),
]# Global BMesh cache system
BMESH_CACHE = {}
CACHE_STATS = {"hits": 0, "misses": 0, "section_objects": set()}

# --- Nowe klasy dla zarządzania warstwami DXF ---

class MIIXARCH_LayerProperty(bpy.types.PropertyGroup):
    name: StringProperty(
        name="Nazwa warstwy",
        description="Nazwa warstwy DXF",
        default=""
    )
    
    line_color_type: EnumProperty(
        name="Typ koloru linii",
        items=[
            ('INDEX', 'Indeks (1-256)', 'Kolor z palety DXF'),
            ('RGB', 'RGB', 'Kolor RGB'),
            ('PRONEKO', 'Proneko', 'Predefiniowane kolory Proneko')
        ],
        default='INDEX'
    )
    
    line_color_index: IntProperty(
        name="Kolor linii (indeks)",
        description="Kolor linii DXF (1-256)",
        default=7,
        min=1,
        max=256
    )
    
    line_color_rgb: FloatVectorProperty(
        name="Kolor linii (RGB)",
        description="Kolor linii RGB",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0
    )
    
    line_color_proneko: EnumProperty(
        name="Kolor linii (Proneko)",
        description="Predefiniowany kolor linii Proneko",
        items=[(key, name, desc) for key, name, desc, rgb in PRONEKO_COLORS],
        default='BLACK'
    )
    
    hatch_color_type: EnumProperty(
        name="Typ koloru hatchu",
        items=[
            ('INDEX', 'Indeks (1-256)', 'Kolor z palety DXF'),
            ('RGB', 'RGB', 'Kolor RGB'),
            ('PRONEKO', 'Proneko', 'Predefiniowane kolory Proneko')
        ],
        default='INDEX'
    )
    
    hatch_color_index: IntProperty(
        name="Kolor hatchu (indeks)",
        description="Kolor hatchu DXF (1-256)",
        default=7,
        min=1,
        max=256
    )
    
    hatch_color_rgb: FloatVectorProperty(
        name="Kolor hatchu (RGB)",
        description="Kolor hatchu RGB",
        subtype='COLOR',
        default=(0.5, 0.5, 0.5),
        min=0.0,
        max=1.0
    )
    
    hatch_color_proneko: EnumProperty(
        name="Kolor hatchu (Proneko)",
        description="Predefiniowany kolor hatchu Proneko",
        items=[(key, name, desc) for key, name, desc, rgb in PRONEKO_COLORS],
        default='BLACK'
    )
    
    line_weight: IntProperty(
        name="Grubość linii",
        description="Grubość linii (0.13-2.0mm jako 13-200)",
        default=13,
        min=5,
        max=200
    )
    
    line_type: EnumProperty(
        name="Typ linii",
        description="Typ linii DXF",
        items=[
            ('CONTINUOUS', 'Continuous', 'Linia ciągła'),
            ('DASHED', 'Dashed', 'Linia kreskowana'),
            ('DASHDOT', 'DashDot', 'Linia kreskowo-kropkowa'),
            ('DOTTED', 'Dotted', 'Linia kropkowana'),
            ('DASHEDX2', 'DashedX2', 'Linia kreskowana podwójna'),
            ('DASHDOT2', 'DashDot2', 'Linia kreskowo-kropkowa podwójna'),
            ('CENTER', 'Center', 'Linia środkowa'),
            ('HIDDEN', 'Hidden', 'Linia ukryta'),
            ('PHANTOM', 'Phantom', 'Linia fantomowa'),
            ('BORDER', 'Border', 'Linia obramowania'),
            ('DIVIDE', 'Divide', 'Linia podziału'),
        ],
        default='CONTINUOUS'
    )
    
    line_scale: FloatProperty(
        name="Skala linii",
        description="Skala typu linii",
        default=1.0,
        min=0.1,
        max=10.0
    )
    
    hatch_weight: IntProperty(
        name="Grubość hatchu",
        description="Grubość linii hatchu",
        default=13,
        min=5,
        max=200
    )
    
    hatch_pattern: EnumProperty(
        name="Wzór hatchu",
        description="Wzór kreskowania DXF",
        items=[
            ('SOLID', 'Solid', 'Wypełnienie solid'),
            ('ANSI31', 'ANSI31', 'Linie ukośne 45°'),
            ('ANSI32', 'ANSI32', 'Linie ukośne 45° przeciwne'),
            ('ANSI33', 'ANSI33', 'Linie ukośne krzyżujące'),
            ('ANSI34', 'ANSI34', 'Linie ukośne gęste'),
            ('ANSI35', 'ANSI35', 'Linie ukośne rzadkie'),
            ('ANSI36', 'ANSI36', 'Linie poziome'),
            ('ANSI37', 'ANSI37', 'Linie pionowe'),
            ('ANSI38', 'ANSI38', 'Siatka'),
            ('DOTS', 'Dots', 'Kropki'),
            ('LINE', 'Line', 'Linie poziome'),
            ('NET', 'Net', 'Siatka kwadratowa'),
            ('PLAST', 'Plast', 'Plastik'),
            ('STEEL', 'Steel', 'Stal'),
            ('BRICK', 'Brick', 'Cegła'),
            ('SAND', 'Sand', 'Piasek'),
            ('EARTH', 'Earth', 'Ziemia'),
        ],
        default='SOLID'
    )
    
    hatch_scale: FloatProperty(
        name="Skala hatchu",
        description="Skala wzoru hatchu",
        default=1.0,
        min=0.1,
        max=10.0
    )
    
    hatch_rotation: FloatProperty(
        name="Obrót hatchu",
        description="Obrót wzoru hatchu w stopniach",
        default=0.0,
        min=0.0,
        max=360.0
    )
    
    # Właściwość kontrolująca rozwinięcie warstwy w panelu
    expanded: BoolProperty(
        name="Rozwinięta",
        description="Czy warstwa jest rozwinięta w panelu",
        default=False
    )


def get_proneko_color_rgb(color_key):
    """Zwraca kolor RGB (0-1) dla klucza koloru Proneko"""
    for key, name, desc, rgb in PRONEKO_COLORS:
        if key == color_key:
            return tuple(c/255.0 for c in rgb)
    return (0.5, 0.5, 0.5)  # Domyślny szary

# --- SYSTEM EKSPORTU/IMPORTU WARSTW DO TEXT BLOKU -------------------------

def export_layers_to_text():
    """Eksportuje warstwy DXF do Text bloku w Blenderze"""
    import json
    
    scene = bpy.context.scene
    if not hasattr(scene, 'miixarch_dxf_layers'):
        return {'CANCELLED'}, "Brak warstw do eksportu"
    
    # Zbierz dane wszystkich warstw
    layers_data = []
    for layer in scene.miixarch_dxf_layers:
        layer_dict = {
            'name': layer.name,
            'line_color_type': layer.line_color_type,
            'line_color_index': layer.line_color_index,
            'line_color_rgb': list(layer.line_color_rgb),
            'line_color_proneko': layer.line_color_proneko,
            'hatch_color_type': layer.hatch_color_type,
            'hatch_color_index': layer.hatch_color_index,
            'hatch_color_rgb': list(layer.hatch_color_rgb),
            'hatch_color_proneko': layer.hatch_color_proneko,
            'line_weight': layer.line_weight,
            'line_type': layer.line_type,
            'line_scale': layer.line_scale,
            'hatch_weight': layer.hatch_weight,
            'hatch_pattern': layer.hatch_pattern,
            'hatch_scale': layer.hatch_scale,
            'hatch_rotation': layer.hatch_rotation,
            'expanded': layer.expanded
        }
        layers_data.append(layer_dict)
    
    # Utwórz/zaktualizuj Text blok
    text_name = "MIIX_DXF_Layers.json"
    if text_name in bpy.data.texts:
        text_block = bpy.data.texts[text_name]
    else:
        text_block = bpy.data.texts.new(text_name)
    
    # Zapisz dane jako JSON
    json_data = {
        'version': '1.0',
        'created': bpy.path.basename(bpy.data.filepath),
        'layers': layers_data
    }
    
    text_block.clear()
    text_block.write(json.dumps(json_data, indent=2, ensure_ascii=False))
    
    return {'FINISHED'}, f"Eksportowano {len(layers_data)} warstw do '{text_name}'"

def import_layers_from_text():
    """Importuje warstwy DXF z Text bloku w Blenderze"""
    import json
    
    text_name = "MIIX_DXF_Layers.json"
    if text_name not in bpy.data.texts:
        return {'CANCELLED'}, f"Nie znaleziono Text bloku '{text_name}'"
    
    text_block = bpy.data.texts[text_name]
    try:
        json_data = json.loads(text_block.as_string())
    except json.JSONDecodeError as e:
        return {'CANCELLED'}, f"Błąd parsowania JSON: {e}"
    
    if 'layers' not in json_data:
        return {'CANCELLED'}, "Nieprawidłowy format danych"
    
    scene = bpy.context.scene
    
    # Wyczyść istniejące warstwy
    scene.miixarch_dxf_layers.clear()
    
    # Dodaj warstwy z Text bloku
    imported_count = 0
    for layer_data in json_data['layers']:
        try:
            new_layer = scene.miixarch_dxf_layers.add()
            new_layer.name = layer_data.get('name', f'Layer_{imported_count}')
            new_layer.line_color_type = layer_data.get('line_color_type', 'INDEX')
            new_layer.line_color_index = layer_data.get('line_color_index', 7)
            new_layer.line_color_rgb = layer_data.get('line_color_rgb', [0.5, 0.5, 0.5])
            new_layer.line_color_proneko = layer_data.get('line_color_proneko', 'BLACK')
            new_layer.hatch_color_type = layer_data.get('hatch_color_type', 'INDEX')
            new_layer.hatch_color_index = layer_data.get('hatch_color_index', 7)
            new_layer.hatch_color_rgb = layer_data.get('hatch_color_rgb', [0.5, 0.5, 0.5])
            new_layer.hatch_color_proneko = layer_data.get('hatch_color_proneko', 'BLACK')
            new_layer.line_weight = layer_data.get('line_weight', 13)
            new_layer.line_type = layer_data.get('line_type', 'CONTINUOUS')
            new_layer.line_scale = layer_data.get('line_scale', 1.0)
            new_layer.hatch_weight = layer_data.get('hatch_weight', 13)
            new_layer.hatch_pattern = layer_data.get('hatch_pattern', 'SOLID')
            new_layer.hatch_scale = layer_data.get('hatch_scale', 1.0)
            new_layer.hatch_rotation = layer_data.get('hatch_rotation', 0.0)
            new_layer.expanded = layer_data.get('expanded', False)
            imported_count += 1
        except Exception as e:
            debug_log(f"Błąd importu warstwy {layer_data.get('name', 'unknown')}: {e}")
    
    return {'FINISHED'}, f"Zaimportowano {imported_count} warstw z '{text_name}'"

def auto_export_layers_to_text():
    """Automatyczny eksport warstw do Text bloku przy każdej zmianie"""
    try:
        export_layers_to_text()
    except Exception as e:
        debug_log(f"Błąd automatycznego eksportu warstw: {e}")

def auto_import_layers_from_text():
    """Automatyczny import warstw z Text bloku przy otwieraniu pliku"""
    try:
        text_name = "MIIX_DXF_Layers.json"
        if text_name in bpy.data.texts and not bpy.context.scene.miixarch_dxf_layers:
            result, message = import_layers_from_text()
            if result == {'FINISHED'}:
                debug_log(f"Auto-import warstw: {message}")
    except Exception as e:
        debug_log(f"Błąd automatycznego importu warstw: {e}")

# --- SYSTEM CACHE DXF -------------------------------------------------------

    import json
import hashlib
from datetime import datetime

# Globalny cache w pamięci dla szybkiego dostępu
_dxf_memory_cache = {}
_cache_file_path = None

def get_cache_text_block():
    """Zwraca lub tworzy Text blok dla cache DXF"""
    cache_name = "MIIX_DXF_Cache"
    
    # Sprawdź czy Text blok już istnieje
    if cache_name in bpy.data.texts:
        return bpy.data.texts[cache_name]
    
    # Utwórz nowy Text blok
    cache_text = bpy.data.texts.new(cache_name)
    cache_text.from_string(json.dumps({
        'version': '1.0',
        'blend_file': bpy.data.filepath,
        'last_updated': datetime.now().isoformat(),
        'objects': {}
    }, indent=2, ensure_ascii=False))
    
    return cache_text

def get_cache_file_path():
    """Zwraca ścieżkę do pliku cache obok pliku .blend (zachowana dla kompatybilności)"""
    global _cache_file_path
    if _cache_file_path:
        return _cache_file_path
    
    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        blend_name = os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        _cache_file_path = os.path.join(blend_dir, f"{blend_name}.miix_dxf_cache.json")
        return _cache_file_path
    return None

def calculate_object_fingerprint(obj):
    """Oblicza unikalny fingerprint obiektu na podstawie geometrii i ustawień"""
    if obj.type not in ['MESH', 'FONT']:
        return None
    
    try:
        # Podstawowe dane obiektu
        fingerprint_data = {
            'name': obj.name,
            'type': obj.type,
            'transform': [list(row) for row in obj.matrix_world],
        }
        
        # DXF settings z Custom Properties (będą dodane później)
        fingerprint_data['dxf_settings'] = {
            'layer': obj.get("miix_dxf_layer", ""),
            'boundary_edges': obj.get("miix_dxf_boundary_edges", True),
            'internal_edges': obj.get("miix_dxf_internal_edges", False),
            'hatches': obj.get("miix_dxf_hatches", True),
        }
        
        # Geometry data
        if obj.type == 'MESH':
            deps = bpy.context.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(deps)
            mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps)
            
            try:
                # Hash vertices i faces - tylko podstawowe dane
                fingerprint_data['geometry'] = {
                    'vertex_count': len(mesh.vertices),
                    'face_count': len(mesh.polygons),
                    'edge_count': len(mesh.edges),
                    'bbox': [list(obj.bound_box[i]) for i in range(8)]
                }
            finally:
                bpy.data.meshes.remove(mesh)
                
        elif obj.type == 'FONT':
            # Dla fontów - tekst, rozmiar, font
            fingerprint_data['font_data'] = {
                'body': obj.data.body,
                'size': obj.data.size,
                'font': obj.data.font.name if obj.data.font else 'default',
                'offset': obj.data.offset,
                'extrude': obj.data.extrude,
                'bevel_depth': obj.data.bevel_depth,
            }
        
        # Oblicz hash
        json_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.md5(json_str.encode()).hexdigest()
        
    except Exception as e:
        debug_log(f"Błąd obliczania fingerprint dla {obj.name}: {e}")
        return None

def load_dxf_cache():
    """Ładuje cache z Text bloku Blendera"""
    global _dxf_memory_cache
    
    try:
        cache_text = get_cache_text_block()
        if cache_text and cache_text.as_string():
            _dxf_memory_cache = json.loads(cache_text.as_string())
            debug_log(f"Cache załadowany z Text bloku: {len(_dxf_memory_cache.get('objects', {}))} obiektów")
            return _dxf_memory_cache
    except Exception as e:
        debug_log(f"Błąd ładowania cache z Text bloku: {e}")
    
    # Fallback - utwórz nowy cache
    _dxf_memory_cache = {
        'version': '1.0',
        'blend_file': bpy.data.filepath,
        'last_updated': datetime.now().isoformat(),
        'objects': {}
    }
    return _dxf_memory_cache

def save_dxf_cache():
    """Zapisuje cache do Text bloku Blendera"""
    global _dxf_memory_cache
    
    if not _dxf_memory_cache:
        return False
    
    try:
        _dxf_memory_cache['last_updated'] = datetime.now().isoformat()
        _dxf_memory_cache['blend_file'] = bpy.data.filepath
        
        cache_text = get_cache_text_block()
        cache_json = json.dumps(_dxf_memory_cache, indent=2, ensure_ascii=False)
        cache_text.from_string(cache_json)
        
        debug_log(f"Cache zapisany do Text bloku: {len(_dxf_memory_cache.get('objects', {}))} obiektów")
        return True
    except Exception as e:
        debug_log(f"Błąd zapisu cache do Text bloku: {e}")
        return False

def get_cached_geometry(obj):
    """Pobiera cached geometry dla obiektu"""
    global _dxf_memory_cache
    
    if not _dxf_memory_cache:
        load_dxf_cache()
    
    obj_name = obj.name
    if obj_name not in _dxf_memory_cache.get('objects', {}):
        return None
    
    cached_obj = _dxf_memory_cache['objects'][obj_name]
    current_fingerprint = calculate_object_fingerprint(obj)
    
    if current_fingerprint != cached_obj.get('fingerprint'):
        debug_log(f"Cache nieaktualny dla {obj_name} - fingerprint się zmienił")
        return None
    
    debug_log(f"Używam cache dla {obj_name}")
    return cached_obj.get('cached_geometry')

def cache_object_geometry(obj, geometry_data):
    """Zapisuje geometry obiektu do cache"""
    global _dxf_memory_cache
    
    if not _dxf_memory_cache:
        load_dxf_cache()
    
    fingerprint = calculate_object_fingerprint(obj)
    if not fingerprint:
        return False
    
    obj_name = obj.name
    _dxf_memory_cache['objects'][obj_name] = {
        'fingerprint': fingerprint,
        'last_modified': datetime.now().isoformat(),
        'type': obj.type,
        'layer_name': obj.get("miix_dxf_layer", ""),
        'dxf_settings': {
            'boundary_edges': obj.get("miix_dxf_boundary_edges", True),
            'internal_edges': obj.get("miix_dxf_internal_edges", False),
            'hatches': obj.get("miix_dxf_hatches", True),
        },
        'cached_geometry': geometry_data
    }
    
    debug_log(f"Cache: zapisano geometrię dla {obj_name} (vertices: {len(geometry_data.get('vertices', []))}, edges: {len(geometry_data.get('edges', []))}, type: {geometry_data.get('export_type', 'unknown')})")
    
    # Zapisz cache do Text bloku
    save_dxf_cache()
    return True

def invalidate_object_cache(obj_name):
    """Usuwa obiekt z cache (np. gdy został zmodyfikowany)"""
    global _dxf_memory_cache
    
    if not _dxf_memory_cache:
        return
    
    if obj_name in _dxf_memory_cache.get('objects', {}):
        del _dxf_memory_cache['objects'][obj_name]
        debug_log(f"Cache invalidated dla {obj_name}")

def get_dxf_cache_statistics():
    """Zwraca statystyki cache"""
    global _dxf_memory_cache
    
    if not _dxf_memory_cache:
        load_dxf_cache()
    
    total_objects = len(_dxf_memory_cache.get('objects', {}))
    cache_size_kb = 0
    cache_location = "Brak"
    
    try:
        cache_text = get_cache_text_block()
        if cache_text and cache_text.as_string():
            cache_size_kb = len(cache_text.as_string().encode('utf-8')) / 1024
            cache_location = f"Text blok: {cache_text.name}"
    except:
        pass
    
    return {
        'total_objects': total_objects,
        'cache_size_kb': cache_size_kb,
        'cache_location': cache_location,
        'cache_file': None  # Zachowana dla kompatybilności
    }

# --- KONIEC SYSTEMU CACHE DXF -----------------------------------------------

# --- Funkcje obsługi Custom Properties dla DXF -----------------------------

def get_object_dxf_layer(obj):
    """Pobiera nazwę warstwy DXF z Custom Properties obiektu"""
    return obj.get("miix_dxf_layer", "")

def set_object_dxf_layer(obj, layer_name):
    """Ustawia nazwę warstwy DXF w Custom Properties obiektu"""
    obj["miix_dxf_layer"] = layer_name

def get_object_boundary_edges(obj):
    """Pobiera ustawienie krawędzi brzegowych z Custom Properties"""
    return obj.get("miix_dxf_boundary_edges", True)

def set_object_boundary_edges(obj, value):
    """Ustawia ustawienie krawędzi brzegowych w Custom Properties"""
    obj["miix_dxf_boundary_edges"] = value

def get_object_internal_edges(obj):
    """Pobiera ustawienie krawędzi wewnętrznych z Custom Properties"""
    return obj.get("miix_dxf_internal_edges", False)

def set_object_internal_edges(obj, value):
    """Ustawia ustawienie krawędzi wewnętrznych w Custom Properties"""
    obj["miix_dxf_internal_edges"] = value

def get_object_hatches(obj):
    """Pobiera ustawienie kreskowania z Custom Properties"""
    return obj.get("miix_dxf_hatches", True)

def set_object_hatches(obj, value):
    """Ustawia ustawienie kreskowania w Custom Properties"""
    obj["miix_dxf_hatches"] = value

def get_object_cache_key(obj, operation_type, origin=None, normal=None, cam_params=None):
    """Tworzy unikalny klucz cache dla obiektu i operacji"""
    try:
        # Hash bazujący na nazwie obiektu i matrix_world
        matrix_hash = hash(tuple(tuple(row) for row in obj.matrix_world))
        
        # Dodaj geometrię mesh do hash (jeśli dostępna)
        if hasattr(obj, 'data') and hasattr(obj.data, 'vertices'):
            vertex_count = len(obj.data.vertices)
            poly_count = len(obj.data.polygons)
            geom_hash = hash((vertex_count, poly_count))
        else:
            geom_hash = 0
            
        # Dodaj parametry specyficzne dla typu obiektu
        type_hash = 0
        if obj.type == 'FONT':
            # Dla fontów uwzględnij tekst i parametry czcionki
            font_data = (
                getattr(obj.data, 'body', ''),
                getattr(obj.data, 'size', 1.0),
                getattr(obj.data, 'resolution_u', 3),
                str(getattr(obj.data, 'font', 'default')),
                getattr(obj.data, 'extrude', 0.0),
                getattr(obj.data, 'bevel_depth', 0.0)
            )
            type_hash = hash(font_data)
        elif obj.type == 'MESH':
            # Dla mesh dodaj hash modyfikatorów
            modifiers = tuple(mod.name for mod in obj.modifiers)
            type_hash = hash(modifiers)
            
        # Dodaj parametry operacji
        origin_hash = hash(tuple(origin)) if origin else 0
        normal_hash = hash(tuple(normal)) if normal else 0
        cam_hash = hash(str(cam_params)) if cam_params else 0
        
        return f"{obj.name}_{operation_type}_{matrix_hash}_{geom_hash}_{type_hash}_{origin_hash}_{normal_hash}_{cam_hash}"
        
    except Exception:
        # W przypadku błędu, zwróć unikalny klucz
        import time
        return f"{obj.name}_{operation_type}_{time.time()}"

def clear_bmesh_cache():
    """Czyści cache bmesh"""
    global BMESH_CACHE, CACHE_STATS
    BMESH_CACHE.clear()
    CACHE_STATS = {"hits": 0, "misses": 0, "section_objects": set()}

def get_cache_stats():
    """Zwraca statystyki cache"""
    total = CACHE_STATS["hits"] + CACHE_STATS["misses"]
    if total > 0:
        hit_rate = (CACHE_STATS["hits"] / total) * 100
        return f"Cache: {CACHE_STATS['hits']} hit, {CACHE_STATS['misses']} miss ({hit_rate:.1f}% hit rate)"
    return "Cache: brak statystyk"



# -----------------------------------------------------------------------------
# MIIX Architektura - ENUM Functions -----------------------------------------
# -----------------------------------------------------------------------------

def get_area_items(self, context):
    return [(c.name, c.name.split(".", 1)[-1], "") for c in bpy.data.collections
            if c.name.startswith("#Obszar.") and "-" not in c.name and "_" not in c.name]

def get_building_items(self, context):
    return [(c.name, c.name.split(".", 1)[-1], "") for c in bpy.data.collections
            if c.name.startswith("#Budynek.") and "_" not in c.name]

def get_object_type_items(self, context):
    items = [
        ("#Teren", "Teren", ""),
        ("#Deski_tarasowe", "Deski tarasowe", ""),
        ("#Kostka_betonowa", "Kostka betonowa", ""),
        ("#Kostka_farmerska", "Kostka farmerska", ""),
        ("#Ogród_deszczowy", "Ogród deszczowy", ""),
        ("#Ogród_zimowy", "Ogród zimowy", ""),
        ("#Opaska_żwirowa", "Opaska żwirowa", ""),
        ("#Ekokrata", "Ekokrata", ""),
        ("#Oś", "Oś", ""),
        ("#Przekrój", "Przekrój", "")
    ]
    return items

def get_layer_items(self, context):
    """Zwraca listę dostępnych warstw dla EnumProperty - sortowane alfabetycznie"""
    # Pobierz warstwy ze sceny
    layers = context.scene.miixarch_dxf_layers
    items = [('NONE', 'Brak', 'Brak warstwy')]
    
    # Zbierz warstwy ze sceny i posortuj alfabetycznie
    scene_layers = []
    for layer in layers:
        if layer.name:
            scene_layers.append((layer.name, layer.name, f"Warstwa: {layer.name}"))
    
    # Sortuj alfabetycznie po nazwie warstwy (drugi element tupli)
    scene_layers.sort(key=lambda x: x[1].lower())
    items.extend(scene_layers)
    
    # Jeśli nie ma warstw w scenie, użyj domyślnych z OBSZARY_LAYERS
    if len(scene_layers) == 0:
        fallback_layers = []
        for layer_key in OBSZARY_LAYERS.keys():
            layer_data = OBSZARY_LAYERS[layer_key]
            layer_name = layer_data.get("layer", layer_key)
            fallback_layers.append((layer_key, layer_name, f"Warstwa: {layer_name}"))
        
        # Sortuj alfabetycznie
        fallback_layers.sort(key=lambda x: x[1].lower())
        items.extend(fallback_layers)
    
    return items

def update_rename_target_from_selection(self, context):
    if context.scene.miixarch_building_enum:
        context.scene.miixarch_rename_target = context.scene.miixarch_building_enum
    if context.scene.miixarch_area_enum:
        context.scene.miixarch_area_name = context.scene.miixarch_area_enum

# --- POWIERZCHNIA ---

surface_types = [
    ('Powierzchnia_netto_uzytkowa', "Powierzchnia netto użytkowa", ""),
    ('Powierzchnia_netto_wewnetrzna', "Powierzchnia netto wewnętrzna", ""),
    ('Powierzchnia_brutto_calkowita', "Powierzchnia brutto całkowita", ""),
    ('Powierzchnia_brutto_zabudowy', "Powierzchnia brutto zabudowy", ""),
    ('Orth', 'Orth', ''),
    ('Elewacja', 'Elewacja', ''),
    ('Pir', 'Pir', ''),
    ('Porotherm', 'Porotherm', ''),
    ('Silikat', 'Silikat', ''),
    ('Styropian', 'Styropian', ''),
    ('Styrodur', 'Styrodur', ''),
    ('Wełna', 'Wełna', ''),
    ('Żelbet', 'Żelbet', ''),
    ('Beton', 'Beton', ''),
    ('Drewno', 'Drewno', ''),
]

# Lista materiałów/warstw dla panelu BUDYNKI - WARSTWY
MATERIAL_TYPES = [
    "Balustrada", "Beton", "Drewno", "Drzwi", "Elewacja", "Meble", "Okna", 
    "Orth", "Oś", "Pir", "Porotherm", "Powierzchnie - brutto","Powierzchnie - netto", "Powierzchnie - tekst", 
    "Przekrój", "Silikat", "Styrodur", "Styropian", "Wełna", "Żelbet"
]

def get_objects_by_material_type(material_type):
    """Zwraca obiekty odpowiadające danemu typowi materiału."""
    objects = []
    
    if material_type == "Powierzchnie - tekst":
        # Obiekty Font z "Powierzchnia" w nazwie + ich dzieci
        for obj in bpy.data.objects:
            if obj.type == 'FONT' and "Powierzchnia" in obj.name:
                objects.append(obj)
                # Dodaj dzieci
                objects.extend(obj.children)
    elif material_type == "Powierzchnie - brutto":
        # Obiekty MESH z "Powierzchnia" w nazwie, ale NIE dzieci obiektów Font
        for obj in bpy.data.objects:
            if (obj.type == 'MESH' and "Powierzchnia-brutto" in obj.name and 
                not (obj.parent and obj.parent.type == 'FONT')):
                objects.append(obj)
    elif material_type == "Powierzchnie - netto":
        # Obiekty MESH z "Powierzchnia" w nazwie, ale NIE dzieci obiektów Font
        for obj in bpy.data.objects:
            if (obj.type == 'MESH' and "Powierzchnia-netto" in obj.name and 
                not (obj.parent and obj.parent.type == 'FONT')):
                objects.append(obj)
    elif material_type == "Drzwi":
        # Szukaj obiektów z nazwą "#Stolarka_drzwi"
        for obj in bpy.data.objects:
            if "#Stolarka_drzwi" in obj.name:
                objects.append(obj)
    elif material_type == "Okna":
        # Szukaj obiektów z nazwą "#Stolarka_okno"
        for obj in bpy.data.objects:
            if "#Stolarka_okno" in obj.name:
                objects.append(obj)
    elif material_type == "Meble":
        # Szukaj obiektów z nazwą "#Meble"
        for obj in bpy.data.objects:
            if "#Meble" in obj.name:
                objects.append(obj)
    elif material_type == "Oś":
        # Szukaj obiektów z nazwą "#Oś"
        for obj in bpy.data.objects:
            if "#Oś" in obj.name or "#Os" in obj.name:
                objects.append(obj)
    elif material_type == "Przekrój":
        # Szukaj obiektów z nazwą "#Przekrój"
        for obj in bpy.data.objects:
            if "#Przekrój" in obj.name or "#Przekroj" in obj.name:
                objects.append(obj)
    else:
        # Standardowe materiały - wszystkie obiekty z tym słowem w nazwie
        for obj in bpy.data.objects:
            if material_type in obj.name:
                objects.append(obj)
    
    return objects

def calculate_area(obj):
    if obj.type == 'MESH':
        return sum(f.area for f in obj.data.polygons)
    elif obj.type == 'CURVE':
        return 0
    return 0

def calculate_area_xy(obj):
    # Oblicza powierzchnię rzutowaną na XY
    if obj.type == 'MESH':
        import mathutils
        area = 0.0
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        for poly in mesh.polygons:
            verts = [mesh.vertices[i].co for i in poly.vertices]
            verts2d = [(v.x, v.y) for v in verts]
            n = len(verts2d)
            a = 0.0
            for i in range(n):
                x1, y1 = verts2d[i]
                x2, y2 = verts2d[(i+1)%n]
                a += (x1*y2 - x2*y1)
            area += abs(a) / 2.0
        obj.to_mesh_clear()
        return area
    return 0.0

def calculate_area_xy_with_ostab(obj):
    """Oblicza powierzchnię z uwzględnieniem grupy vertex '#OSTAB'."""
    if obj.type != 'MESH':
        return {"Powierzchnia": 0.0}
    
    # Sprawdź czy obiekt ma grupę vertex "#OSTAB"
    ostab_group = None
    for vg in obj.vertex_groups:
        if vg.name == "#OSTAB":
            ostab_group = vg
            break
    
    # Jeśli nie ma grupy OSTAB, zwróć standardową powierzchnię
    if not ostab_group:
        area = calculate_area_xy(obj)
        return {"Powierzchnia": round(area, 4)}
    
    # Oblicz powierzchnie z podziałem na OSTAB i poza OSTAB
    import mathutils
    area_ostab = 0.0
    area_non_ostab = 0.0
    
    mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    
    # Sprawdź każdy face
    for poly in mesh.polygons:
        verts = [mesh.vertices[i].co for i in poly.vertices]
        verts2d = [(v.x, v.y) for v in verts]
        n = len(verts2d)
        a = 0.0
        for i in range(n):
            x1, y1 = verts2d[i]
            x2, y2 = verts2d[(i+1)%n]
            a += (x1*y2 - x2*y1)
        face_area = abs(a) / 2.0
        
        # Sprawdź czy face należy do grupy OSTAB
        # Face należy do grupy jeśli wszystkie jego wierzchołki mają wagę > 0.5 w tej grupie
        vertices_in_ostab = 0
        for vert_index in poly.vertices:
            vertex = mesh.vertices[vert_index]
            for group in vertex.groups:
                if group.group == ostab_group.index and group.weight > 0.5:
                    vertices_in_ostab += 1
                    break
        
        # Jeśli wszystkie wierzchołki face'a należą do OSTAB
        if vertices_in_ostab == len(poly.vertices):
            area_ostab += face_area
        else:
            area_non_ostab += face_area
    
    obj.to_mesh_clear()
    
    area_total = area_ostab + area_non_ostab
    
    return {
        "Powierzchnia w obrębie OSTAB": round(area_ostab, 4),
        "Powierzchnia poza OSTAB": round(area_non_ostab, 4),
        "Powierzchnia razem": round(area_total, 4)
    }

def calculate_volume(obj):
    # Oblicza objętość mesh
    if obj.type == 'MESH':
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        volume = 0.0
        for poly in mesh.polygons:
            v1 = mesh.vertices[poly.vertices[0]].co
            for i in range(1, len(poly.vertices) - 1):
                v2 = mesh.vertices[poly.vertices[i]].co
                v3 = mesh.vertices[poly.vertices[i+1]].co
                volume += v1.cross(v2).dot(v3)
        obj.to_mesh_clear()
        return abs(volume) / 6.0
    return 0.0

def calculate_depth(obj):
    # Głębokość po osi Z
    if obj.type == 'MESH':
        mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
        zs = [v.co.z for v in mesh.vertices]
        obj.to_mesh_clear()
        if zs:
            return max(zs) - min(zs)
    return 0.0

def calculate_largest_face_area_xy(obj):
    """Oblicza powierzchnię największego face w układzie XY."""
    if obj.type != 'MESH' or not obj.data.polygons:
        return 0.0
    
    import bmesh
    
    # Pobierz cache key
    cache_key = get_object_cache_key(obj, "largest_face_area_xy")
    
    if cache_key in BMESH_CACHE:
        CACHE_STATS["hits"] += 1
        return BMESH_CACHE[cache_key]
    
    CACHE_STATS["misses"] += 1
    
    try:
        # Utwórz bmesh z obiektu
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bm.transform(obj.matrix_world)
        
        max_area = 0.0
        
        for face in bm.faces:
            if len(face.verts) >= 3:
                # Pobierz współrzędne wierzchołków face w układzie XY
                xy_coords = [(v.co.x, v.co.y) for v in face.verts]
                
                # Oblicz powierzchnię używając wzoru shoelace
                area = 0.0
                n = len(xy_coords)
                for i in range(n):
                    j = (i + 1) % n
                    area += xy_coords[i][0] * xy_coords[j][1]
                    area -= xy_coords[j][0] * xy_coords[i][1]
                area = abs(area) / 2.0
                
                if area > max_area:
                    max_area = area
        
        bm.free()
        
        # Zapisz w cache
        BMESH_CACHE[cache_key] = max_area
        
        return max_area
        
    except Exception:
        return 0.0

# --- OBSŁUGA STRUKTURY ---

def rename_structure(old_prefix, new_prefix):
    for c in bpy.data.collections:
        if c.name.startswith(old_prefix):
            c.name = c.name.replace(old_prefix, new_prefix, 1)
    for o in bpy.data.objects:
        if o.name.startswith(old_prefix):
            o.name = o.name.replace(old_prefix, new_prefix, 1)

def ensure_building_structure(base_name, storeys):
    base = bpy.data.collections.get(base_name)
    if not base:
        base = bpy.data.collections.new(base_name)
        bpy.context.scene.collection.children.link(base)
    def make_sub(name):
        sub = bpy.data.collections.get(name)
        if not sub:
            sub = bpy.data.collections.new(name)
            base.children.link(sub)
        empty = bpy.data.objects.get(name)
        if not empty:
            empty = bpy.data.objects.new(name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 1.0
            empty.location = (0, 0, 0)
            sub.objects.link(empty)
    make_sub(f"{base_name}_Fundament")
    make_sub(f"{base_name}_Dach")
    for i in range(1, storeys + 1):
        make_sub(f"{base_name}_Kondygnacja.{i}")
    # Usuń nadmiarowe kondygnacje
    i = storeys + 1
    while True:
        name = f"{base_name}_Kondygnacja.{i}"
        coll = bpy.data.collections.get(name)
        if not coll:
            break
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(coll)
        i += 1

def ensure_area_structure(base_name):
    base = bpy.data.collections.get(base_name)
    if not base:
        base = bpy.data.collections.new(base_name)
        bpy.context.scene.collection.children.link(base)

    def make_sub(name, parent):
        sub = bpy.data.collections.get(name)
        if not sub:
            sub = bpy.data.collections.new(name)
            parent.children.link(sub)
        empty = bpy.data.objects.get(name)
        if not empty:
            empty = bpy.data.objects.new(name, None)
            empty.empty_display_type = 'PLAIN_AXES'
            empty.empty_display_size = 1.0
            empty.location = (0, 0, 0)
            sub.objects.link(empty)
        return sub

    # Dane i jej podkolekcje
    dane = make_sub(f"{base_name}-Dane", base)
    for sub in ["Działki", "Linie_zabudowy", "Mapa", "Granice"]:
        make_sub(f"{base_name}-{sub}", dane)

    # Budynki bezpośrednio pod Obszarem
    make_sub(f"{base_name}-Budynki", base)

    # Teren i jej podkolekcje
    teren = make_sub(f"{base_name}-Teren", base)
    for t in ["Opaski", "Mury", "Ogrodzenia", "Wiaty", "Drogi", "Chodniki", "Podjazdy", "Parkingi", "Tarasy", "Ogródki", "Skarpy", "Wody", "Zieleń", "Place_zabaw"]:
        make_sub(f"{base_name}-{t}", teren)

    # Uzbrojenie i jej podkolekcje
    uzb = make_sub(f"{base_name}-Uzbrojenie", base)
    for u in ["Woda", "Kanalizacja_sanitarna", "Kanalizacja_deszczowa", "Ciepło", "Gaz", "Elektryka", "Teletechnika"]:
        make_sub(f"{base_name}-{u}", uzb)

    # Opis i jej podkolekcje
    uzb = make_sub(f"{base_name}-Opis", base)
    for u in ["Opis-Ogólne", "Opis-Koordynacja", "Opis-Analizy", "Opis-Uzbrojenie", "Opis-Deszcz", "Opis-Wymiary", "Opis-Przekroje"]:
        make_sub(f"{base_name}-{u}", uzb)

# -----------------------------------------------------------------------------
# Stałe -----------------------------------------------------------------------
COS_TOL    = 0.999962
SCALE_DXF  = 100.0
LINE_SCALE = 1.0
HATCH_LW   = 9
HATCH_CLR  = 7   # ⟵ zmieniony z 1
MERGE_TOL  = 1e-6  # tolerancja łączenia końców linii

LAYER_CFG = {
    "orth": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-orth", "weight": 30, "color": 7,
                      "pattern": "ANSI32", "scale": 1.0, "solid_color": (190,192,186)},
        "widok":    {"layer": "PNK_AR_01_widok-orth",   "weight": 13, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-orth",     "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "elewacja": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-elewacja",  "weight": 13, "color": 7,
                      "pattern": "SOLID", "scale": 1.0, "solid_color": (204,204,204)},
        "widok":    {"layer": "PNK_AR_01_widok-elewacja",    "weight": 13, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-elewacja",      "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "pir": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-pir",  "weight": 13, "color": 7,
                      "pattern": "ANSI37", "scale": 1.0, "solid_color": (204,204,204)},
        "widok":    {"layer": "PNK_AR_01_widok-pir",    "weight": 13, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-pir",      "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "porotherm": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-porotherm", "weight": 30, "color": 7,
                      "pattern": "ANSI31", "scale": 2.0, "solid_color": (190,192,186)},
        "widok":    {"layer": "PNK_AR_01_widok-porotherm",   "weight": 30, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-porotherm",     "weight": 30, "color": 7,
                      "linetype": "DASHED2"},
    },
    "silikat": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-silikat", "weight": 30, "color": 7,
                      "pattern": "AR-SAND", "scale": 0.2, "solid_color": (190,192,186)},
        "widok":    {"layer": "PNK_AR_01_widok-silikat",   "weight": 30, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-silikat",     "weight": 30, "color": 7,
                      "linetype": "DASHED2"},
    },
    "styropian": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-styropian", "weight": 13, "color": 7,
                      "pattern": "HONEY", "scale": 2.0, "solid_color": (204,204,204)},
        "widok":    {"layer": "PNK_AR_01_widok-styropian",   "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "styrodur": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-styrodur", "weight": 13, "color": 7,
                      "pattern": "HONEY", "scale": 2.0, "solid_color": (204,204,204)},
        "widok":    {"layer": "PNK_AR_01_widok-styrodur",   "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "welna": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-welna", "weight": 13, "color": 7,
                      "pattern": "INSUL", "scale": 2.0, "angle": 45, "solid_color": 40},
        "widok":    {"layer": "PNK_AR_01_widok-welna",   "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "zelbet": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-zelbet", "weight": 30, "color": 7,
                      "pattern": "ANSI33", "scale": 2.0, "solid_color": (153,153,153)},
        "widok":    {"layer": "PNK_AR_01_widok-zelbet",   "weight": 30, "color": 7,
                      "linetype": "CONTINUOUS"},
        "nad":      {"layer": "PNK_AR_01_nad-zelbet",     "weight": 30, "color": 7,
                      "linetype": "DASHED"},
    },
    "beton": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-beton", "weight": 30, "color": 7,
                      "pattern": "ANSI36", "scale": 1.0, "solid_color": (190,192,186)},
        "widok":    {"layer": "PNK_AR_01_widok-beton",   "weight": 13, "color": 7},
        "nad":      {"layer": "PNK_AR_01_nad-beton",     "weight": 13, "color": 7,
                      "linetype": "DASHED2"},
    },
    "drewno": {
        "przekroj": {"layer": "PNK_AR_01_przekroj-drewno", "weight": 30, "color": 7,
                      "pattern": "ANSI32", "scale": 2.0, "solid_color": 32},
        "widok":    {"layer": "PNK_AR_01_widok-drewno",   "weight": 30, "color": 7,
                      "linetype": "DASHEDX2"},
        "nad":      {"layer": "PNK_AR_01_nad-drewno",     "weight": 30, "color": 7,
                      "linetype": "DASHED"},
    },
    "os": {
        "przekroj": {"layer": "PNK_AR_03_opis_osi", "weight": 30, "color": (206,22,22),
                      "linetype": "CENTER", "no_hatch": True},
        "widok":    {"layer": "PNK_AR_03_opis_osi", "weight": 30, "color": (206,22,22),
                      "linetype": "CENTER", "no_hatch": True},
        "nad":      {"layer": "PNK_AR_03_opis_osi", "weight": 30, "color": (206,22,22),
                      "linetype": "CENTER", "no_hatch": True},
    },
    "przekroj": {
        "przekroj": {"layer": "PNK_AR_03_ogolne_opis_przekroje", "weight": 50, "color": (206,22,22),
                      "linetype": "DASHED", "no_hatch": True},
        "widok":    {"layer": "PNK_AR_03_ogolne_opis_przekroje", "weight": 50, "color": (206,22,22),
                      "linetype": "DASHED", "no_hatch": True},
        "nad":      {"layer": "PNK_AR_03_ogolne_opis_przekroje", "weight": 50, "color": (206,22,22),
                      "linetype": "DASHED", "no_hatch": True},
    },
    "opis_konstrukcja": {
        "przekroj": {"layer": "PNK_AR_03_opis_konstrukcja", "weight": 9, "color": (206,22,22)},
        "widok":    {"layer": "PNK_AR_03_opis_konstrukcja", "weight": 9, "color": (206,22,22)},
        "nad":      {"layer": "PNK_AR_03_opis_konstrukcja", "weight": 9, "color": (206,22,22)},
    },
    "meble": {
        "przekroj": {"layer": "PNK_AR_02_meble", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "widok":    {"layer": "PNK_AR_02_meble", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "nad":      {"layer": "PNK_AR_02_meble", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
    },
    "stolarka_drzwi": {
        "przekroj": {"layer": "PNK_AR_02_drzwi", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "widok":    {"layer": "PNK_AR_02_drzwi", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "nad":      {"layer": "PNK_AR_02_drzwi", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
    },
    "stolarka_okna": {
        "przekroj": {"layer": "PNK_AR_02_okna", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "widok":    {"layer": "PNK_AR_02_okna", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "nad":      {"layer": "PNK_AR_02_okna", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
    },
    "balustrada": {
        "przekroj": {"layer": "PNK_AR_02_balustrady", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "widok":    {"layer": "PNK_AR_02_balustrady", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
        "nad":      {"layer": "PNK_AR_02_balustrady", "weight": 9, "color": 7,
                      "linetype": "CONTINUOUS"},
    },
}

# --- Nowe stałe dla warstw obszarów ------------------------------------------
OBSZARY_LAYERS = {
    "dzialki": {"layer": "PNK_ZT_01_projekt_dzialki", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "linie_zabudowy": {"layer": "PNK_ZT_01_mpzp_linia-zabudowy", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "granice": {"layer": "PNK_ZT_01_projekt_obszar-opracowania", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "mury": {"layer": "PNK_ZT_02_mury", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "BRICK", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "ogrodzenia": {"layer": "PNK_ZT_02_ogrodzenia", "color": 7, "weight": 100, "linetype": "DOTTED", "hatch_pattern": "ANSI31", "hatch_scale": 0.5, "hatch_rotation": 45.0},
    "wiaty": {"layer": "PNK_ZT_02_wiaty", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_rgb": (153,153,153), "hatch_pattern": "ANSI31", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "drogi": {"layer": "PNK_ZT_02_drogi", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "chodniki": {"layer": "PNK_ZT_02_chodniki", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "DOTS", "hatch_scale": 0.5, "hatch_rotation": 0.0},
    "podjazdy": {"layer": "PNK_ZT_02_podjazdy", "color": 7, "weight": 25, "linetype": "CONTINUOUS", "hatch_pattern": "ANSI32", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "parkingi": {"layer": "PNK_ZT_02_parkingi", "color": 7, "weight": 25, "linetype": "CONTINUOUS", "hatch_pattern": "ANSI36", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "tarasy": {"layer": "PNK_ZT_02_tarasy", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "ANSI37", "hatch_scale": 0.5, "hatch_rotation": 0.0},
    "ogrodki": {"layer": "PNK_ZT_02_ogrodki", "color": 7, "weight": 70, "linetype": "DOTTED", "hatch_pattern": "EARTH", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "skarpy": {"layer": "PNK_ZT_02_skarpy", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SAND", "hatch_scale": 1.0, "hatch_rotation": 30.0},
    "zieleń": {"layer": "PNK_ZT_02_zielen", "color": 7, "weight": 9, "linetype": "CONTINUOUS", "hatch_pattern": "EARTH", "hatch_scale": 0.8, "hatch_rotation": 0.0},
    "opaski": {"layer": "PNK_ZT_02_opaski", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "ANSI31", "hatch_scale": 0.3, "hatch_rotation": 45.0},
    "place_zabaw": {"layer": "PNK_ZT_02_place_zabaw", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SAND", "hatch_scale": 0.5, "hatch_rotation": 0.0},
    "wody": {"layer": "PNK_ZT_02_wody", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "ANSI37", "hatch_scale": 0.3, "hatch_rotation": 0.0},
    "parter": {"layer": "PNK_ZT_02_budynki_parter", "color": 7, "weight": 9, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "wyzsze_kondygnacje": {"layer": "PNK_ZT_02_budynki_nadziemne", "color": 7, "weight": 35, "linetype": "DASHEDX2", "hatch_pattern": "ANSI31", "hatch_scale": 0.5, "hatch_rotation": 45.0},
    "opis_rzedna": {"layer": "PNK_ZT_04_opis-ogolne_rzedne", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "dachy": {"layer": "PNK_ZT_02_budynki_dach", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "edges_only": True, "boundary_edges_only": True, "hatch_pattern": "ANSI31", "hatch_scale": 1.0, "hatch_rotation": 30.0},
    "klatki_schodowe": {"layer": "PNK_ZT_02_klatki-schodowe", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_rgb": (255,255,255), "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_spadek": {"layer": "PNK_ZT_04_opis-ogolne_spadki", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_wejscie": {"layer": "PNK_ZT_04_opis-ogolne_wejscia", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_wjazd": {"layer": "PNK_ZT_04_opis-ogolne_wjazdy", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_rgb": (255,255,255), "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Woda
    "w_instalacje": {"layer": "PNK_ZT_03_w_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "w_sieci": {"layer": "PNK_ZT_03_w_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "w_przylacza": {"layer": "PNK_ZT_03_w_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_w": {"layer": "PNK_ZT_04_opis-uzbrojenie_w", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Kanalizacja sanitarna
    "ks_instalacje": {"layer": "PNK_ZT_03_ks_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "ks_sieci": {"layer": "PNK_ZT_03_ks_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "ks_przylacza": {"layer": "PNK_ZT_03_ks_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_ks": {"layer": "PNK_ZT_04_opis-uzbrojenie_ks", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Kanalizacja deszczowa
    "kd_instalacje": {"layer": "PNK_ZT_03_kd_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "kd_sieci": {"layer": "PNK_ZT_03_kd_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "kd_przylacza": {"layer": "PNK_ZT_03_kd_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_kd": {"layer": "PNK_ZT_04_opis-uzbrojenie_kd", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Ciepło
    "co_instalacje": {"layer": "PNK_ZT_03_co_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "co_sieci": {"layer": "PNK_ZT_03_co_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "co_przylacza": {"layer": "PNK_ZT_03_co_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_co": {"layer": "PNK_ZT_04_opis-uzbrojenie_co", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Gaz
    "gaz_instalacje": {"layer": "PNK_ZT_03_gaz_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "gaz_sieci": {"layer": "PNK_ZT_03_gaz_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "gaz_przylacza": {"layer": "PNK_ZT_03_gaz_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_gaz": {"layer": "PNK_ZT_04_opis-uzbrojenie_gaz", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Elektryka
    "en_instalacje": {"layer": "PNK_ZT_03_en_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "en_sieci": {"layer": "PNK_ZT_03_en_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "en_przylacza": {"layer": "PNK_ZT_03_en_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_en": {"layer": "PNK_ZT_04_opis-uzbrojenie_en", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Teletechnika
    "tt_instalacje": {"layer": "PNK_ZT_03_tt_instalacje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "tt_sieci": {"layer": "PNK_ZT_03_tt_sieci", "color": 7, "weight": 70, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "tt_przylacza": {"layer": "PNK_ZT_03_tt_przylacza", "color": 7, "weight": 50, "linetype": "DASHDOT2", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_tt": {"layer": "PNK_ZT_04_opis-uzbrojenie_tt", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    # Nowe warstwy dla opisów
    "opis_uzbrojenie_kd": {"layer": "PNK_ZT_04_opis-uzbrojenie_kd", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_poziom": {"layer": "PNK_ZT_04_opis-ogolne_rzedne", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_deszcz": {"layer": "PNK_ZT_04_opis-deszcz", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_przekroje": {"layer": "PNK_ZT_04_opis-przekroje", "color": 7, "weight": 35, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_przekroje_font": {"layer": "PNK_ZT_04_opis-przekroje", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "opis_ogolne": {"layer": "PNK_ZT_04_opis-ogolne", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "layout": {"layer": "PNK_00_layout", "color": 7, "weight": 13, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
    "warstwice": {"layer": "PNK_ZT_02_warstwice", "color": 7, "weight": 5, "linetype": "CONTINUOUS", "hatch_pattern": "SOLID", "hatch_scale": 1.0, "hatch_rotation": 0.0},
}

def _should_export_edge(e, obj_n, mesh):
    """Eksportuj krawędź, jeśli jest na brzegu (1 face) lub kąt między normalnymi > 20 stopni."""
    # Sprawdź ile ścian jest połączonych z krawędzią (Blender 4.3 fix)
    v1, v2 = e.vertices
    connected_faces = [poly for poly in mesh.polygons if v1 in poly.vertices and v2 in poly.vertices]
    
    if len(connected_faces) == 1:
        return True  # outline
    if len(connected_faces) != 2:
        return False  # nieoczekiwany przypadek (np. mesh error)
    
    # Sprawdź kąt między normalnymi
    n1 = obj_n @ connected_faces[0].normal
    n2 = obj_n @ connected_faces[1].normal
    cos_angle = n1.normalized().dot(n2.normalized())
    angle_deg = math.degrees(math.acos(max(min(cos_angle, 1.0), -1.0)))
    return angle_deg > 20

def normalize_polish_chars(text):
    """Normalizuje polskie znaki do wersji bez diakrytyków."""
    replacements = {
        'ą': 'a', 'ć': 'c', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ó': 'o', 'ś': 's', 'ź': 'z', 'ż': 'z',
        'Ą': 'A', 'Ć': 'C', 'Ę': 'E', 'Ł': 'L', 'Ń': 'N', 'Ó': 'O', 'Ś': 'S', 'Ź': 'Z', 'Ż': 'Z'
    }
    for polish, latin in replacements.items():
        text = text.replace(polish, latin)
    return text

def rgb_to_truecolor_int(rgb):
    """Zamienia tuple RGB na int dla DXF (group code 420)."""
    r, g, b = rgb
    return (r << 16) + (g << 8) + b

def get_obszar_type_from_collection(coll_name):
    name = coll_name.lower()
    if "działki" in name or "dzialki" in name:
        return "dzialki"
    if "-linie_zabudowy" in name:
        return "linie_zabudowy"
    if "-granice" in name:
        return "granice"
    if "-mury" in name:
        return "mury"
    if "-ogrodzenia" in name:
        return "ogrodzenia"
    if "-wiaty" in name:
        return "wiaty"
    if "-drogi" in name:
        return "drogi"
    if "-chodniki" in name:
        return "chodniki"
    if "-podjazdy" in name:
        return "podjazdy"
    if "-parkingi" in name:
        return "parkingi"
    if "-tarasy" in name:
        return "tarasy"
    if "-ogrodki" in name:
        return "ogrodki"
    if "-skarpy" in name:
        return "skarpy"
    if "-zieleń" in name or "-zielen" in name:
        return "zieleń"
    if "-opaski" in name:
        return "opaski"
    if "-place_zabaw" in name:
        return "place_zabaw"
    if "-wody" in name:
        return "wody"
    if "-budynki" in name:
        return "budynki"
    return None

def get_obszar_type_from_object_name(obj_name):
    """Rozpoznaje typ obszaru na podstawie nazwy obiektu."""
    name = obj_name.lower()
    # Kondygnacje
    if "kondygnacja" in name and any(c.isdigit() for c in name):
        # Sprawdź czy to kondygnacja wyższa niż parter (2, 3, 4...)
        import re
        match = re.search(r'kondygnacja\.?(\d+)', name)
        if match:
            level = int(match.group(1))
            if level == 1:
                return "parter"
            elif level >= 2:
                return "wyzsze_kondygnacje"
    # Dachy
    if "dach" in name:
        return "dachy"
    # Klatki schodowe
    if "klatki_schodowe" in name or "klatka_schodowa" in name:
        return "klatki_schodowe"    # Parter
    if "parter" in name:
        return "parter"
    return None

def get_uzbrojenie_type(obj_name, collections, for_edges=False):
    """Rozpoznaje typ uzbrojenia na podstawie nazwy obiektu i kolekcji."""
    name = obj_name.lower()
    
    # Określ typ obiektu
    obj_type = None
    if "#instalacje" in name:
        obj_type = "instalacje"
    elif "#sieci" in name:
        obj_type = "sieci"
    elif "#przyłącza" in name or "#przylacza" in name:
        obj_type = "przylacza"
    
    if not obj_type:
        return None
    
    # Określ medium na podstawie kolekcji
    medium = None
    is_opis = False
    
    for coll in collections:
        coll_name = coll.name.lower()
        # Sprawdź czy to kolekcja Opis
        if "opis" in coll_name:
            is_opis = True
        
        # Sprawdź medium
        if "woda" in coll_name and "kanalizacja" not in coll_name:
            medium = "w"
        elif "kanalizacja_sanitarna" in coll_name or "kanalizacja sanitarna" in coll_name:
            medium = "ks"
        elif "kanalizacja_deszczowa" in coll_name or "kanalizacja deszczowa" in coll_name:
            medium = "kd"
        elif "ciepło" in coll_name or "cieplo" in coll_name:
            medium = "co"
        elif "gaz" in coll_name:
            medium = "gaz"
        elif "elektryka" in coll_name or "energia" in coll_name:
            medium = "en"
        elif "teletechnika" in coll_name:
            medium = "tt"
    
    if not medium:
        return None
    
    # Jeśli obiekt jest w kolekcji Opis
    if is_opis:
        # W PASS 3 (for_edges=True) nie przetwarzamy opisów
        if for_edges:
            return None
        return f"opis_{medium}"
    else:
        return f"{medium}_{obj_type}"

def get_special_opis_type(obj_name, collections):
    """Rozpoznaje specjalne typy opisów na podstawie nazwy obiektu i kolekcji."""
    name = obj_name.lower()
    
    # Sprawdź obiekty z "#opis-poziom" w nazwie
    if "#opis-poziom" in name:
        return "opis_poziom"
    
    # Sprawdź obiekty z "#opis-spadek" w nazwie
    if "#opis-spadek" in name:
        return "opis_spadek"
    
    # Sprawdź obiekty "etykieta" w kolekcji "Opis-Ogólne"
    if "etykieta" in name:
        for coll in collections:
            if "opis-ogólne" in coll.name.lower() or "opis-ogolne" in coll.name.lower():
                return "opis_ogolne"
    
    # Sprawdź kolekcje dla innych opisów
    for coll in collections:
        coll_name = coll.name.lower()
        if "opis-uzbrojenie-kanalizacja_deszczowa" in coll_name:
            return "opis_uzbrojenie_kd"
        elif "opis-deszcz" in coll_name:
            return "opis_deszcz"
        elif "opis-przekroje" in coll_name:
            # Rozróżnij między mesh a font dla różnych grubości
            return "opis_przekroje"
    
    return None

def _add_obszar_layer(doc, name, color, weight, linetype=None):
    if name in doc.layers:
        return
    
    if isinstance(color, tuple):
        layer = doc.layers.new(name)
        layer.dxf.true_color = rgb_to_truecolor_int(color)
        layer.dxf.lineweight = weight
        if linetype:
            layer.dxf.linetype = linetype
    else:
        doc.layers.new(name, dxfattribs={
            "color": color,
            "lineweight": weight,
            **({"linetype": linetype} if linetype else {})
        })

# -----------------------------------------------------------------------------
# Parser nazwy ➜ warstwa -------------------------------------------------------
# -----------------------------------------------------------------------------
_strip = lambda t: "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).lower()
CATEGORY_RE = re.compile(r"#?(orth|elewacja|pir|porotherm|silikat|styropian|styrodur|wełna|welna|żelbet|zelbet|drewno|beton|os|oś|meble|stolarka_drzwi|stolarka_okna|balustrada|przekroj|przekrój)", re.I)
KIND_RE     = re.compile(r"_(przekroj|przekrój|widok|nad)$", re.I)
OPIS_RE     = re.compile(r"#?opis-konstrukcja", re.I)

def parse_layer_from_name(name: str):
    """Parsuje nazwę obiektu i zwraca konfigurację warstwy."""

    
    # Normalizuj polskie znaki
    stripped = normalize_polish_chars(name.lower())

    
    # Sprawdź czy to obiekt kategorii (os, przekroj)
    category_match = re.search(r'#(os|oś|przekroj|przekrój)', stripped)
    if category_match:
        kind = category_match.group(1)
        if kind in ['os', 'oś']:
            kind = 'os'
        elif kind in ['przekroj', 'przekrój']:
            kind = 'przekroj'
        # Zwróć konfigurację z LAYER_CFG - dla obiektów bez sufiksu użyj 'przekroj'
        layer_config = LAYER_CFG.get(kind, {}).get('przekroj')
        if layer_config:
            return layer_config
        else:
            return {"layer": "0"}
    
    # Sprawdź czy to obiekt z sufiksem _przekroj, _widok, _nad lub _special (z opcjonalnymi numerami)
    kind_match = re.search(r'_(przekroj|przekrój|widok|nad|special)(?:\.\d+)?$', stripped)
    if kind_match:
        kind = kind_match.group(1)
        if kind in ['przekroj', 'przekrój']:
            kind = 'przekroj'
        elif kind == 'special':
            # Dla obiektów _special, sprawdź czy to #Oś czy #Przekrój i użyj odpowiedniej konfiguracji
            if '#oś' in stripped or '#os' in stripped:
                kind = 'przekroj'  # Używamy konfiguracji przekroj dla osi (wszystkie suffixe mają tę samą warstwę)
                category_kind = 'os'
                layer_config = LAYER_CFG.get(category_kind, {}).get(kind)
                if layer_config:
                    return layer_config
            elif '#przekroj' in stripped or '#przekrój' in stripped:
                kind = 'przekroj'  # Używamy konfiguracji przekroj dla przekrojów
                category_kind = 'przekroj'
                layer_config = LAYER_CFG.get(category_kind, {}).get(kind)
                if layer_config:
                    return layer_config
        
        # Najpierw sprawdź czy to obiekt kategorii (os, przekroj) z suffixem
        category_match = re.search(r'#(os|oś|przekroj|przekrój)', stripped)
        if category_match:
            category_kind = category_match.group(1)
            if category_kind in ['os', 'oś']:
                category_kind = 'os'
            elif category_kind in ['przekroj', 'przekrój']:
                category_kind = 'przekroj'
            # Zwróć konfigurację z LAYER_CFG dla kategorii (wszystkie suffixe mają tę samą warstwę)
            layer_config = LAYER_CFG.get(category_kind, {}).get(kind)
            if layer_config:
                return layer_config
        
        # Jeśli nie kategoria, sprawdź typ materiału z nazwy
        material_type = None
        material_patterns = {
            'zelbet': r'#(żelbet|zelbet)',
            'styropian': r'#styropian',
            'styrodur': r'#styrodur', 
            'welna': r'#(wełna|welna)',
            'porotherm': r'#porotherm',
            'silikat': r'#silikat',
            'orth': r'#orth',
            'beton': r'#beton',
            'posadzka': r'#posadzka',
            'elewacja': r'#elewacja',
            'drewno': r'#drewno',
            'pir': r'#pir'
        }
        
        for mat_type, pattern in material_patterns.items():
            if re.search(pattern, stripped):
                material_type = mat_type
                break
        
        if material_type:
            # Pobierz konfigurację warstwy
            layer_config = LAYER_CFG.get(material_type, {}).get(kind)
            if layer_config:
                return layer_config
        
        # Fallback - zwróć podstawową konfigurację
        return {"layer": "0"}
    
    return None

# -----------------------------------------------------------------------------
# Płaszczyzna przekroju --------------------------------------------------------
# -----------------------------------------------------------------------------

def get_cutting_plane(ctx):
    cam = ctx.scene.camera
    if not cam or cam.type != 'CAMERA':
        return None
    mw = cam.matrix_world
    normal = (mw.to_quaternion() @ Vector((0, 0, -1))).normalized()
    origin = mw.translation + normal * cam.data.clip_start
    return cam, origin, normal

# -----------------------------------------------------------------------------
# Mesh generatory --------------------------------------------------------------
# -----------------------------------------------------------------------------

def _new_mesh_from_bmesh(bm, name, coll):
    if not bm.verts and not bm.edges:
        return None
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh); bm.free()
    ob = bpy.data.objects.new(name, mesh)
    props = parse_layer_from_name(name)
    ob["miix_layer"] = props["layer"] if props else "0"
    coll.objects.link(ob)
    return ob


def section_mesh(src_obj, origin, normal, coll):
    """Cached wersja section_mesh z wykluczaniem obiektów"""
    global CACHE_STATS
    
    # Specjalne obiekty #Oś i #Przekrój są obsługiwane przez special_mesh()
    is_special = '#Oś' in src_obj.name or '#Os' in src_obj.name or '#Przekrój' in src_obj.name or '#Przekroj' in src_obj.name
    if is_special:
        return None
    
    # Sprawdź cache
    cache_key = get_object_cache_key(src_obj, "section", origin, normal)
    
    if cache_key in BMESH_CACHE:
        CACHE_STATS["hits"] += 1
        cached_data = BMESH_CACHE[cache_key]
        
        if cached_data is None:
            # Obiekt nie ma przekroju (cached negative result)
            return None
            
        # Odtwórz mesh z cache
        section_name = src_obj.name + "_przekroj"
        mesh = bpy.data.meshes.new(section_name)
        mesh.from_pydata(cached_data["vertices"], cached_data["edges"], cached_data["faces"])
        mesh.update()
        
        ob = bpy.data.objects.new(section_name, mesh)
        props = parse_layer_from_name(section_name)
        ob["miix_layer"] = props["layer"] if props else "0"
        coll.objects.link(ob)
        
        # Zaznacz że obiekt ma przekrój
        CACHE_STATS["section_objects"].add(src_obj.name)
        return ob
    
    # Cache MISS - oblicz normalnie
    CACHE_STATS["misses"] += 1
    
    # Oryginalna logika section_mesh
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = src_obj.evaluated_get(deps)
    src = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
    
    # Wczesne sprawdzenie czy ma polygony
    if not src.polygons:
        if not is_special:
            # Dla zwykłych obiektów brak polygonów oznacza brak przekroju
            bpy.data.meshes.remove(src)
            BMESH_CACHE[cache_key] = None  # Cache negative result
            return None
        else:
            # Dla obiektów #Oś / #Przekrój kontynuuj – będziemy ciąć same krawędzie
            pass
    
    bm = bmesh.new()
    bm.from_mesh(src)
    
    # Transform geometry to world space 
    bm.transform(eval_obj.matrix_world)
    
    # Szybki bisect - tylko dodaj krawędzie przecięcia
    result = bmesh.ops.bisect_plane(bm,
        geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
        plane_co=origin, plane_no=normal,
        use_snap_center=False, clear_outer=False, clear_inner=False)
    
    # Zbierz krawędzie na płaszczyźnie z jednym przejściem
    tolerance = 1e-4  # Większa tolerancja = szybsze
    plane_edges = []
    
    for e in bm.edges:
        v1_dist = abs((e.verts[0].co - origin).dot(normal))
        v2_dist = abs((e.verts[1].co - origin).dot(normal))
        if v1_dist < tolerance and v2_dist < tolerance:
            plane_edges.append(e)
    
    if not plane_edges:
        if is_special:
            pass
        bm.free()
        bpy.data.meshes.remove(src)
        BMESH_CACHE[cache_key] = None  # Cache negative result
        return None
    
    # Utwórz mesh bez fill (najwolniejsza operacja)
    bm_cut = bmesh.new()
    vmap = {}
    
    for e in plane_edges:
        pts = [v.co.copy() for v in e.verts]
        keys = [tuple(round(c, 5) for c in p) for p in pts]  # Mniejsza precyzja = szybsze
        if keys[0] == keys[1]: 
                continue
        
        verts = []
        for key, p in zip(keys, pts):
            vert = vmap.get(key)
            if vert is None:
                vert = bm_cut.verts.new(p)
                vmap[key] = vert
            verts.append(vert)
        
        try: 
            bm_cut.edges.new(tuple(verts))
        except ValueError: 
            pass
    
    # Wypełnij powierzchnie dla hatchy - szybka wersja
    if bm_cut.edges:
        try:
            # Tylko holes_fill - szybsze niż edgenet_fill
            bmesh.ops.holes_fill(bm_cut, edges=bm_cut.edges[:])
        except Exception:
            pass  # Jeśli fill się nie uda, eksportuj same krawędzie
    
    result_obj = None
    if bm_cut.verts:
        section_name = src_obj.name + "_przekroj"
        
        if is_special:
            pass
        
        # Zapisz do cache przed utworzeniem obiektu
        cache_data = {
            "vertices": [v.co[:] for v in bm_cut.verts],
            "edges": [[v.index for v in e.verts] for e in bm_cut.edges],
            "faces": [[v.index for v in f.verts] for f in bm_cut.faces]
        }
        BMESH_CACHE[cache_key] = cache_data
        
        result_obj = _new_mesh_from_bmesh(bm_cut, section_name, coll)
        
        # Zaznacz że obiekt ma przekrój
        CACHE_STATS["section_objects"].add(src_obj.name)
    else:
        if is_special:
            pass
        bm_cut.free()
        BMESH_CACHE[cache_key] = None  # Cache negative result
    
    bm.free()
    bpy.data.meshes.remove(src)
    return result_obj

def special_mesh(src_obj, coll, suffix="_special"):
    """Generuje obiekt ze wszystkimi krawędziami dla obiektów #Oś i #Przekrój"""
    global CACHE_STATS
    
    
    if not hasattr(src_obj, 'data') or src_obj.data is None:
        return None
    
    
    # Obiekty z samymi edges są OK - to właśnie chcemy eksportować
    
    # Sprawdź cache
    cache_key = get_object_cache_key(src_obj, "special")
    if cache_key in BMESH_CACHE:
        cached_data = BMESH_CACHE[cache_key]
        if cached_data is None:
            CACHE_STATS["hits"] += 1
            return None
        else:
            CACHE_STATS["hits"] += 1
            # Odtwórz obiekt z cache
            bm = bmesh.new()
            for v_co in cached_data["vertices"]:
                bm.verts.new(v_co)
            bm.verts.ensure_lookup_table()
            for edge_indices in cached_data["edges"]:
                bm.edges.new([bm.verts[i] for i in edge_indices])
            for face_indices in cached_data["faces"]:
                bm.faces.new([bm.verts[i] for i in face_indices])
            
            special_name = src_obj.name + suffix
            result_obj = _new_mesh_from_bmesh(bm, special_name, coll)
            bm.free()
            return result_obj
    
    CACHE_STATS["misses"] += 1
    
    # Użyj evaluated mesh jak w innych funkcjach
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = src_obj.evaluated_get(deps)
    src = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
    
    # Utwórz bmesh z całej geometrii
    bm = bmesh.new()
    bm.from_mesh(src)
    
    # Transform geometry to world space 
    bm.transform(eval_obj.matrix_world)
    
    # Usuń tymczasowy mesh
    bpy.data.meshes.remove(src)
    
    result_obj = None
    
    if bm.verts or bm.edges:
        special_name = src_obj.name + suffix
        
        # Zapisz do cache
        cache_data = {
            "vertices": [v.co[:] for v in bm.verts],
            "edges": [[v.index for v in e.verts] for e in bm.edges],
            "faces": [[v.index for v in f.verts] for f in bm.faces]
        }
        BMESH_CACHE[cache_key] = cache_data
        
        result_obj = _new_mesh_from_bmesh(bm, special_name, coll)
        
        if result_obj:
            # Zaznacz że obiekt ma specjalną geometrię
            CACHE_STATS["section_objects"].add(src_obj.name)
        else:
            pass
    else:
        bm.free()
        BMESH_CACHE[cache_key] = None
    
    return result_obj

def depth_mesh(src_obj, cam, origin, normal, coll, ctx, zmin, zmax, suffix):
    """Cached wersja depth_mesh"""
    global CACHE_STATS
    
    # Specjalne obiekty #Oś i #Przekrój są obsługiwane przez special_mesh()
    is_special = '#Oś' in src_obj.name or '#Os' in src_obj.name or '#Przekrój' in src_obj.name or '#Przekroj' in src_obj.name
    if is_special:
        return None
    
    # Sprawdź czy to obiekt Żelbet - dla niego zawsze generujemy widok/nad
    obj_name_lower = src_obj.name.lower()
    is_zelbet = "żelbet" in obj_name_lower or "zelbet" in obj_name_lower
    
    # Sprawdź czy obiekt ma już przekrój - wtedy pomijamy (chyba że to Żelbet)
    if src_obj.name in CACHE_STATS["section_objects"] and not is_zelbet:
        return None
    
    # Sprawdź czy to materiał izolacyjny - pomijamy widok/nad dla tych materiałów
    insulation_materials = ["pir", "styrodur", "styropian", "wełna", "welna"]
    if any(material in obj_name_lower for material in insulation_materials):
        return None
    
    if is_zelbet:
        pass
    else:
        pass
    
    # Przygotuj parametry cache
    cam_params = (
        tuple(tuple(row) for row in cam.matrix_world),
        zmin, zmax, suffix
    )
    cache_key = get_object_cache_key(src_obj, f"depth{suffix}", origin, normal, cam_params)
    
    if cache_key in BMESH_CACHE:
        CACHE_STATS["hits"] += 1
        cached_data = BMESH_CACHE[cache_key]
        
        if cached_data is None:
            # Obiekt nie ma depth mesh (cached negative result)
            return None
            
        # Odtwórz mesh z cache
        depth_name = src_obj.name + suffix
        mesh = bpy.data.meshes.new(depth_name)
        mesh.from_pydata(cached_data["vertices"], cached_data["edges"], [])  # Tylko krawędzie dla depth
        mesh.update()
        
        ob = bpy.data.objects.new(depth_name, mesh)
        props = parse_layer_from_name(depth_name)
        ob["miix_layer"] = props["layer"] if props else "0"
        coll.objects.link(ob)
        
        return ob
    
    # Cache MISS - oblicz normalnie
    CACHE_STATS["misses"] += 1
    
    # Oryginalna logika depth_mesh
    deps = ctx.evaluated_depsgraph_get()
    eval_obj = src_obj.evaluated_get(deps)
    src = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
    
    if not src.edges:
        bpy.data.meshes.remove(src)
        BMESH_CACHE[cache_key] = None  # Cache negative result
        return None
    
    
    bm_src = bmesh.new()
    bm_src.from_mesh(src)
    
    # Cache obliczenia raz
    obj2w = eval_obj.matrix_world
    cam_inv = cam.matrix_world.inverted()
    scene = ctx.scene
    obj_n = obj2w.to_3x3()
    
    # Lambda functions
    project = lambda w: w - ((w-origin).dot(normal)) * normal
    in_fov = lambda v: 0 <= v.x <= 1 and 0 <= v.y <= 1
    
    bm_dst = bmesh.new()
    vmap = {}
    
    # Zoptymalizowana pętla
    for e in bm_src.edges:
        # Sprawdź normalne (jeśli edge ma 2 faces) - Blender 4.3 fix
        v1, v2 = e.verts[0].index, e.verts[1].index
        connected_faces = [f for f in bm_src.faces if v1 in [v.index for v in f.verts] and v2 in [v.index for v in f.verts]]
        
        if len(connected_faces) == 2:
            n1 = obj_n @ connected_faces[0].normal
            n2 = obj_n @ connected_faces[1].normal
            if n1.normalized().dot(n2.normalized()) > COS_TOL: 
                continue
        
        # Transform vertices
        w1, w2 = obj2w @ e.verts[0].co, obj2w @ e.verts[1].co
        
        # Depth test
        z1, z2 = -(cam_inv @ w1).z, -(cam_inv @ w2).z
        if not (zmin <= z1 <= zmax and zmin <= z2 <= zmax): 
                continue
        
        # FOV test
        if not (in_fov(world_to_camera_view(scene, cam, w1)) and in_fov(world_to_camera_view(scene, cam, w2))): 
                continue
        
        # Project points
        p1, p2 = project(w1), project(w2)
        k1, k2 = tuple(round(c, 5) for c in p1), tuple(round(c, 5) for c in p2)  # Mniejsza precyzja
        if k1 == k2: 
                continue
            
        # Create vertices
        v1 = vmap.get(k1)
        if v1 is None:
            v1 = bm_dst.verts.new(p1)
            vmap[k1] = v1
        v2 = vmap.get(k2)
        if v2 is None:
            v2 = bm_dst.verts.new(p2)
            vmap[k2] = v2
        
        try: 
            bm_dst.edges.new((v1, v2))
        except ValueError: 
            pass

    result_obj = None
    if bm_dst.edges:
        # Szybsze remove_doubles
        bmesh.ops.remove_doubles(bm_dst, verts=bm_dst.verts, dist=1e-4)
        
        depth_name = src_obj.name + suffix
        
        # Zapisz do cache przed utworzeniem obiektu
        cache_data = {
            "vertices": [v.co[:] for v in bm_dst.verts],
            "edges": [[v.index for v in e.verts] for e in bm_dst.edges],
            "faces": []  # Depth mesh ma tylko krawędzie
        }
        BMESH_CACHE[cache_key] = cache_data
        
        result_obj = _new_mesh_from_bmesh(bm_dst, depth_name, coll)
    else:
        bm_dst.free()
        BMESH_CACHE[cache_key] = None  # Cache negative result
        
    bm_src.free()
    bpy.data.meshes.remove(src)
    return result_obj

# -----------------------------------------------------------------------------
# DXF – scalanie linii ---------------------------------------------------------
# -----------------------------------------------------------------------------

def _pt_key(pt):
    """Zaokrągla współrzędną do kroku MERGE_TOL w celu łączenia węzłów."""
    return (round(pt[0] / MERGE_TOL) * MERGE_TOL,
            round(pt[1] / MERGE_TOL) * MERGE_TOL)


def _merge_lines_to_polylines(msp):
    """Scala entity LINE w jedną lub więcej `LWPOLYLINE` na warstwę.
    Optymalizowana wersja z limitem czasu.
    """
    import time
    from ezdxf.lldxf import const as dxfconst
    PLINEGEN = getattr(dxfconst, "LWPOLYLINE_PLINEGEN", 128)
    
    start_time = time.time()
    MAX_TIME = 30  # Maximum 30 seconds for line merging

    by_layer = {}
    all_lines = list(msp.query("LINE"))
    
    for ln in all_lines:
        by_layer.setdefault(ln.dxf.layer, []).append(ln)

    for layer, segs in by_layer.items():
        # Skip if taking too long
        if time.time() - start_time > MAX_TIME:
            break
            
        # Limit segments per layer for performance
        if len(segs) > 1000:
            segs = segs[:1000]
            
        raw = [(_pt_key(ln.dxf.start), _pt_key(ln.dxf.end), ln) for ln in segs]
        pending = raw.copy()
        paths = []

        while pending and time.time() - start_time < MAX_TIME:
            s, e, _ = pending.pop()
            path = [s, e]
            grown = True
            max_growth = 100  # Limit path growth for performance
            growth_count = 0
            
            while grown and growth_count < max_growth and time.time() - start_time < MAX_TIME:
                grown = False
                growth_count += 1
                for seg in pending[:]:  # Copy list to avoid modification issues
                    s2, e2, _ = seg
                    if s2 == path[-1]:
                        path.append(e2)
                        pending.remove(seg)
                        grown = True
                        break
                    if e2 == path[-1]:
                        path.append(s2)
                        pending.remove(seg)
                        grown = True
                        break
                    if s2 == path[0]:
                        path.insert(0, e2)
                        pending.remove(seg)
                        grown = True
                        break
                    if e2 == path[0]:
                        path.insert(0, s2)
                        pending.remove(seg)
                        grown = True
                        break
            paths.append(path)

        # Create new polylines
        for pts in paths:
            if time.time() - start_time > MAX_TIME:
                break
            coords = [(x, y) for x, y in pts]
            closed = len(coords) > 2 and coords[0] == coords[-1]
            poly = msp.add_lwpolyline(coords, dxfattribs={
                "layer": layer,
                "ltscale": LINE_SCALE,
            }, close=closed)
            poly.dxf.flags |= PLINEGEN

        # Remove old lines
        for _, _, ln in raw:
            try:
                msp.delete_entity(ln)
            except:
                pass  # Ignore if already deleted

# -----------------------------------------------------------------------------
# DXF eksport -----------------------------------------------------------------
# -----------------------------------------------------------------------------

def set_font_resolution(font_obj, resolution=3):
    """Ustaw rozdzielczość obiektu FONT i zwróć oryginalną wartość."""
    if font_obj.type == 'FONT' and font_obj.data:
        original = font_obj.data.resolution_u
        font_obj.data.resolution_u = resolution
        return original
    return None

def restore_font_resolution(font_obj, original_resolution):
    """Przywróć oryginalną rozdzielczość obiektu FONT."""
    if font_obj.type == 'FONT' and font_obj.data and original_resolution is not None:
        font_obj.data.resolution_u = original_resolution

def _ensure_linetype(doc, name):
    if name in (None, "", "CENTER") or name in doc.linetypes:
        return
    patterns = {"DASHED2": [2.5, -1.25], "DASHEDX2": [5.0, -2.5], "DASHED": [2.0, -2.0]}
    if name in patterns:
        doc.linetypes.new(name, dxfattribs={"description": name, "pattern": patterns[name]})

def _add_layer(doc, name, color, weight, linetype=None):
    if name in doc.layers:
        return
    
    if isinstance(color, tuple):
        layer = doc.layers.new(name)
        layer.dxf.true_color = rgb_to_truecolor_int(color)
        layer.dxf.lineweight = weight
        if linetype:
            layer.dxf.linetype = linetype
    else:
        doc.layers.new(name, dxfattribs={
            "color": color,
            "lineweight": weight,
            **({"linetype": linetype} if linetype else {})
        })

def _group_connected_edges(mesh):
    """Grupuje połączone krawędzie w ciągi dla polilinii."""
    import bmesh
    
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    
    visited_edges = set()
    polylines = []
    
    for edge in bm.edges:
        if edge.index in visited_edges:
                continue
            
        # Rozpocznij nową polilinię od tej krawędzi
        polyline = []
        current_edge = edge
        current_vert = current_edge.verts[0]
        
        # Idź w jedną stronę
        while current_edge and current_edge.index not in visited_edges:
            visited_edges.add(current_edge.index)
            
            # Dodaj wierzchołek do polilini
            if not polyline:
                polyline.append(current_vert.co.copy())
            
            # Znajdź drugi wierzchołek krawędzi
            other_vert = current_edge.verts[1] if current_edge.verts[0] == current_vert else current_edge.verts[0]
            polyline.append(other_vert.co.copy())
            
            # Znajdź następną połączoną krawędź
            next_edge = None
            for next_candidate in other_vert.link_edges:
                if next_candidate != current_edge and next_candidate.index not in visited_edges:
                    # Sprawdź czy ma tylko 2 połączone krawędzie (nie rozgałęzienie)
                    if len([e for e in other_vert.link_edges if e.index not in visited_edges]) <= 2:
                        next_edge = next_candidate
                        break
            
            current_edge = next_edge
            current_vert = other_vert
        
        # Jeśli mamy tylko jeden punkt, sprawdź czy możemy iść w drugą stronę od początkowego edge
        if len(polyline) == 2:
            # Spróbuj iść w drugą stronę od oryginalnej krawędzi
            current_edge = edge
            current_vert = edge.verts[1]  # Druga strona
            temp_polyline = [polyline[0].copy()]  # Zaczynamy od pierwszego punktu
            
            # Znajdź krawędzie w drugą stronę
            while True:
                found_edge = None
                for candidate in current_vert.link_edges:
                    if candidate != edge and candidate.index not in visited_edges:
                        if len([e for e in current_vert.link_edges if e.index not in visited_edges]) <= 2:
                            found_edge = candidate
                            break
                
                if not found_edge:
                    break
                    
                visited_edges.add(found_edge.index)
                other_vert = found_edge.verts[1] if found_edge.verts[0] == current_vert else found_edge.verts[0]
                temp_polyline.insert(0, other_vert.co.copy())  # Dodaj na początek
                current_vert = other_vert
                edge = found_edge
            
            if len(temp_polyline) > 1:
                polyline = temp_polyline + polyline[1:]  # Połącz, unikając duplikacji środkowego punktu
        
        if len(polyline) >= 2:
            polylines.append(polyline)
    
    bm.free()
    return polylines


def export_dxf(ctx, coll):
    if ezdxf is None:
        raise RuntimeError("ezdxf not installed (pip install ezdxf)")

    cam, origin, normal = get_cutting_plane(ctx)
    if not cam:
        raise RuntimeError("No active camera")
    

    
    # Debug: informacje o kamerze
    
    # Sprawdź orientację kamery
    cam_forward_real = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    cam_forward = cam_forward_real.normalized()
    
    # Wektor "w górę" kamery
    cam_up = cam.matrix_world.to_quaternion() @ Vector((0, 1, 0))
    
    # Wektor "w prawo" kamery (iloczyn wektorowy)
    cam_right = cam_forward.cross(cam_up).normalized()
    
    # Popraw wektor "w górę" (może być lekko nieprostopadły)
    cam_up = cam_right.cross(cam_forward).normalized()
    
    
    # Sprawdź czy osie są prostopadłe
    dot_right_up = cam_right.dot(cam_up)
    dot_right_forward = cam_right.dot(cam_forward)
    dot_up_forward = cam_up.dot(cam_forward)
    
    # Sprawdź długości wektorów
    
    # Wybierz metodę transformacji - automatycznie w zależności od orientacji kamery
    cam_forward_z = abs(cam_forward.z)
    USE_ALTERNATIVE_TRANSFORM = cam_forward_z > 0.9  # Dla kamery pionowej użyj alternatywnej metody
    
    def get_transform_func():
        if USE_ALTERNATIVE_TRANSFORM:
            return world_to_camera_2d_alternative
        else:
            return world_to_camera_2d
    
    def world_to_camera_2d(world_point):
        """Transformuje punkt ze świata do 2D w płaszczyźnie kamery."""
        # Wektor od kamery do punktu
        relative = world_point - cam.location
        
        # Projekcja na płaszczyznę kamery (X, Y w przestrzeni kamery)
        x = relative.dot(cam_right)
        y = relative.dot(cam_up)
        
        return (x * SCALE_DXF, y * SCALE_DXF)
    
    def world_to_camera_2d_alternative(world_point):
        """Alternatywna transformacja używająca oryginalnej macierzy kamery."""
        # Transformuj do przestrzeni kamery
        cam_point = cam_inv @ world_point
        
        # Użyj X,Y niezależnie od orientacji kamery
        # Jeśli kamera patrzy w dół, Z staje się "głębokością"
        # Jeśli kamera jest pozioma, może być potrzebna inna kombinacja
        
        # Sprawdź orientację i wybierz odpowiednie osie
        cam_forward_z = abs(cam_forward.z)
        if cam_forward_z > 0.9:  # Kamera pionowa
            return (cam_point.x * SCALE_DXF, cam_point.y * SCALE_DXF)
        else:  # Kamera pozioma - użyj innych osi
            # Dla kamery poziomej, Y może być "głębokością", więc użyj X,Z
            return (cam_point.x * SCALE_DXF, cam_point.z * SCALE_DXF)

    cam_inv = cam.matrix_world.inverted()

    directory = os.path.dirname(bpy.path.abspath(ctx.scene.render.filepath)) or bpy.path.abspath('//') or os.getcwd()
    dxf_path = os.path.join(directory, f"{cam.name}.dxf")

    doc = ezdxf.new(setup=True)
    doc.header["$LTSCALE"] = 10
    msp = doc.modelspace()

    # Twórz warstwy raz
    for cat in LAYER_CFG.values():
        for cfg in cat.values():
            _ensure_linetype(doc, cfg.get("linetype"))
            base = cfg["layer"]
            _add_layer(doc, base, cfg["color"], cfg["weight"], cfg.get("linetype"))
            if "pattern" in cfg:
                _add_layer(doc, base + "_h", HATCH_CLR, HATCH_LW)
    
    # Dodaj warstwy tekstowe
    _add_layer(doc, "PNK_AR_03_tekst", (206,22,22), 9)
    _add_layer(doc, "PNK_AR_03_opis_konstrukcja", 1, 9)
    _add_layer(doc, "PNK_AR_03_ogolne_opis_przekroje", (206,22,22), 13)

    # Funkcja pomocnicza do mapowania nazw obiektów na warstwy
    def get_layer_for_object(obj):
        """Zwraca konfigurację warstwy dla obiektu."""
        name = obj.name
        
        # Użyj parse_layer_from_name która teraz zwraca pełną konfigurację
        layer_config = parse_layer_from_name(name)
        if layer_config:
            return layer_config
        else:
            return {"layer": "0"}

    # Cache obiektów po typach (wszystkie obiekty MESH - linie dla wszystkich)
    mesh_objects = [ob for ob in coll.objects if ob.type == 'MESH']
    
    # PASS 1: Hatche
    hatch_count = 0
    
    # Filtruj obiekty które mają konfigurację warstwy (tylko obiekty przekroju, nie widok ani nad)
    pattern_objects = []
    for ob in coll.objects:
        if ob.type == 'MESH':
            # Wyklucz obiekty z _widok i _nad (także po split: nazwa_widok.001, nazwa_nad.002 itd.)
            if '_widok' in ob.name or '_nad' in ob.name:
                continue
            layer_config = parse_layer_from_name(ob.name)
            if layer_config and layer_config.get("layer", "0") != "0":
                pattern_objects.append(ob)
    
    transform_func = get_transform_func()
    
    for ob in pattern_objects:
        layer_config = get_layer_for_object(ob)
        if not layer_config:
                continue
        
        hatch_layer = layer_config.get("layer", "0")
        props = layer_config
        
        polygon_count = 0
        for poly in ob.data.polygons:
            
            # Transformuj wierzchołki
            poly2d = []
            for vi in poly.vertices:
                world_point = ob.matrix_world @ ob.data.vertices[vi].co
                x, y = transform_func(world_point)
                poly2d.append((x, y))
            
            # Sprawdź czy polygon nie jest zdegenerowany
            if len(poly2d) < 3:
                polygon_count += 1
                continue
            
            # Oblicz bounding box i pole 2D
            xs = [p[0] for p in poly2d]
            ys = [p[1] for p in poly2d]
            bbox_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
            
            # Sprawdź pole używając wzoru shoelace
            def shoelace_area(points):
                n = len(points)
                area = 0.0
                for i in range(n):
                    j = (i + 1) % n
                    area += points[i][0] * points[j][1]
                    area -= points[j][0] * points[i][1]
                return abs(area) / 2.0
            
            shoelace_area_val = shoelace_area(poly2d)
            
            if shoelace_area_val < 1e-6:
                polygon_count += 1
                continue
    
            # Tworz hatche dla KAŻDEGO polygonu
            try:
                # Dodaj sufiks _h dla warstwy hatchy
                hatch_layer_name = hatch_layer + "_h"
                
                # SOLID
                sol = msp.add_hatch(dxfattribs={"layer": hatch_layer_name})
                if isinstance(props.get("solid_color"), tuple):
                    sol.dxf.true_color = rgb_to_truecolor_int(props["solid_color"])
                else:
                    sol.dxf.color = props.get("solid_color", 7)
                sol.paths.add_polyline_path(poly2d, is_closed=True)
                    
                # PATTERN
                hp = msp.add_hatch(dxfattribs={"layer": hatch_layer_name})
                hp.paths.add_polyline_path(poly2d, is_closed=True)
                hp.set_pattern_fill(props.get("pattern", "SOLID"), scale=props.get("scale", 1.0))
                hp.dxf.color = 256

                hatch_count += 1
                
            except Exception as e:
                pass
        polygon_count += 1
    

    # PASS 2: LINES jako polilinie - szybko
    for ob in mesh_objects:
        layer_config = get_layer_for_object(ob)
        base_layer = layer_config.get("layer", "0") if isinstance(layer_config, dict) else "0"
        me = ob.data
        
        # Grupuj połączone krawędzie w polilinie
        polylines = _group_connected_edges(me)
        
        for polyline in polylines:
            # Transformuj punkty do przestrzeni kamery
            pts_cam = []
            for pt in polyline:
                world_pt = ob.matrix_world @ pt
                pts_cam.append(transform_func(world_pt))
            
            # Sprawdź czy to zamknięta polilinia
            is_closed = len(pts_cam) > 2 and (abs(pts_cam[0][0] - pts_cam[-1][0]) < 1e-6 and 
                                             abs(pts_cam[0][1] - pts_cam[-1][1]) < 1e-6)
            
            # Dodaj polilinię do DXF
            if len(pts_cam) >= 2:
                lwpoly = msp.add_lwpolyline(pts_cam, close=is_closed, 
                                 dxfattribs={"layer": base_layer})
                lwpoly.dxf.ltscale = LINE_SCALE

    # PASS 3: TEKST - szybko, bez szczegółowego logowania
    text_objects = [o for o in ctx.scene.objects if o.type == 'FONT' and o.visible_get()]
    
    font_processed = 0
    for ob in text_objects:
        # Pobierz właściwości warstwy
        props = parse_layer_from_name(ob.name)
        if props:
            base_layer = props.get("layer", "0")
        elif OPIS_RE.search(_strip(ob.name)):
            base_layer = "PNK_AR_03_opis_konstrukcja"
        elif "#przekrój-opis" in ob.name.lower() or "#przekroj-opis" in ob.name.lower():
            base_layer = "PNK_AR_03_ogolne_opis_przekroje"
        else:
            base_layer = "PNK_AR_03_tekst"
        
        # Ustaw rozdzielczość i konwertuj
        original_resolution = set_font_resolution(ob)
        
        try:
            deps = ctx.evaluated_depsgraph_get()
            eval_obj = ob.evaluated_get(deps)
            tmp_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps)
            
            # Eksportuj polilinie zamiast pojedynczych krawędzi
            polylines = _group_connected_edges(tmp_mesh)
            
            for polyline in polylines:
                # Transformuj punkty do przestrzeni kamery
                pts_cam = []
                for pt in polyline:
                    world_pt = ob.matrix_world @ pt
                    pts_cam.append(transform_func(world_pt))
                
                # Sprawdź czy to zamknięta polilinia
                is_closed = len(pts_cam) > 2 and (abs(pts_cam[0][0] - pts_cam[-1][0]) < 1e-6 and 
                                                 abs(pts_cam[0][1] - pts_cam[-1][1]) < 1e-6)
                
                # Dodaj polilinię do DXF
                if len(pts_cam) >= 2:
                    # Specjalna obsługa dla #Przekrój-opis - ustaw grubość 13
                    dxf_attribs = {"layer": base_layer}
                    if "#przekrój-opis" in ob.name.lower() or "#przekroj-opis" in ob.name.lower():
                        dxf_attribs["lineweight"] = 13
                    
                    lwpoly = msp.add_lwpolyline(pts_cam, close=is_closed, dxfattribs=dxf_attribs)
                    lwpoly.dxf.ltscale = LINE_SCALE
                
            bpy.data.meshes.remove(tmp_mesh)
        finally:
            restore_font_resolution(ob, original_resolution)
        font_processed += 1


    # PASS 4: MEBLE ze sceny - obiektów które nie są w kolekcji roboczej
    meble_objects = [o for o in ctx.scene.objects if o.type == 'MESH' and o.visible_get() and o.name.startswith('#Meble')]
    
    meble_processed = 0
    for ob in meble_objects:
        # Użyj funkcji mapowania warstw
        layer_config = get_layer_for_object(ob)
        base_layer = layer_config.get("layer", "0") if isinstance(layer_config, dict) else "0"
        
        # Eksportuj krawędzie mesh
        try:
            deps = ctx.evaluated_depsgraph_get()
            eval_obj = ob.evaluated_get(deps)
            tmp_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
            
            if tmp_mesh.edges:
                # Eksportuj polilinie zamiast pojedynczych krawędzi
                polylines = _group_connected_edges(tmp_mesh)
                
                for polyline in polylines:
                    # Transformuj punkty do przestrzeni kamery
                    pts_cam = []
                    for pt in polyline:
                        world_pt = ob.matrix_world @ pt
                        pts_cam.append(transform_func(world_pt))
                    
                    # Sprawdź czy to zamknięta polilinia
                    is_closed = len(pts_cam) > 2 and (abs(pts_cam[0][0] - pts_cam[-1][0]) < 1e-6 and 
                                                     abs(pts_cam[0][1] - pts_cam[-1][1]) < 1e-6)
                    
                    # Dodaj polilinię do DXF
                    if len(pts_cam) >= 2:
                        lwpoly = msp.add_lwpolyline(pts_cam, close=is_closed,
                                                  dxfattribs={"layer": base_layer})
                        lwpoly.dxf.ltscale = LINE_SCALE
                    
            bpy.data.meshes.remove(tmp_mesh)
            meble_processed += 1
        except Exception as e:
                continue


    # PASS 5: OŚ ze sceny - obiektów które nie są w kolekcji roboczej
    os_objects = [o for o in ctx.scene.objects if o.type == 'MESH' and o.visible_get() and ('#Oś' in o.name or '#Os' in o.name)]
    
    os_processed = 0
    for ob in os_objects:
        # Użyj funkcji mapowania warstw
        layer_config = get_layer_for_object(ob)
        base_layer = layer_config.get("layer", "0") if isinstance(layer_config, dict) else "0"
        
        # Eksportuj krawędzie mesh
        try:
            deps = ctx.evaluated_depsgraph_get()
            eval_obj = ob.evaluated_get(deps)
            tmp_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
            
            if tmp_mesh.edges:
                # Eksportuj polilinie zamiast pojedynczych krawędzi
                polylines = _group_connected_edges(tmp_mesh)
                
                for polyline in polylines:
                    # Transformuj punkty do przestrzeni kamery
                    pts_cam = []
                    for pt in polyline:
                        world_pt = ob.matrix_world @ pt
                        pts_cam.append(transform_func(world_pt))
                    
                    # Sprawdź czy to zamknięta polilinia
                    is_closed = len(pts_cam) > 2 and (abs(pts_cam[0][0] - pts_cam[-1][0]) < 1e-6 and 
                                                     abs(pts_cam[0][1] - pts_cam[-1][1]) < 1e-6)
                    
                    # Dodaj polilinię do DXF
                    if len(pts_cam) >= 2:
                        lwpoly = msp.add_lwpolyline(pts_cam, close=is_closed,
                                                  dxfattribs={"layer": base_layer})
                        lwpoly.dxf.ltscale = LINE_SCALE
                    
            bpy.data.meshes.remove(tmp_mesh)
            os_processed += 1
        except Exception as e:
                continue


    # PASS 6: PRZEKRÓJ ze sceny - obiektów które nie są w kolekcji roboczej
    przekroj_objects = [o for o in ctx.scene.objects if o.type == 'MESH' and o.visible_get() and ('#Przekrój' in o.name or '#Przekroj' in o.name)]
    
    przekroj_processed = 0
    for ob in przekroj_objects:
        # Użyj funkcji mapowania warstw
        layer_config = get_layer_for_object(ob)
        base_layer = layer_config.get("layer", "0") if isinstance(layer_config, dict) else "0"
        
        # Eksportuj krawędzie mesh
        try:
            deps = ctx.evaluated_depsgraph_get()
            eval_obj = ob.evaluated_get(deps)
            tmp_mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps, preserve_all_data_layers=False)
            
            if tmp_mesh.edges:
                # Eksportuj polilinie zamiast pojedynczych krawędzi
                polylines = _group_connected_edges(tmp_mesh)
                
                for polyline in polylines:
                    # Transformuj punkty do przestrzeni kamery
                    pts_cam = []
                    for pt in polyline:
                        world_pt = ob.matrix_world @ pt
                        pts_cam.append(transform_func(world_pt))
                    
                    # Sprawdź czy to zamknięta polilinia
                    is_closed = len(pts_cam) > 2 and (abs(pts_cam[0][0] - pts_cam[-1][0]) < 1e-6 and 
                                                     abs(pts_cam[0][1] - pts_cam[-1][1]) < 1e-6)
                    
                    # Dodaj polilinię do DXF
                    if len(pts_cam) >= 2:
                        lwpoly = msp.add_lwpolyline(pts_cam, close=is_closed,
                                                  dxfattribs={"layer": base_layer})
                        lwpoly.dxf.ltscale = LINE_SCALE
                    
            bpy.data.meshes.remove(tmp_mesh)
            przekroj_processed += 1
        except Exception as e:
                continue


    # Polilinie są teraz eksportowane bezpośrednio, nie ma potrzeby łączenia linii
    # _merge_lines_to_polylines(msp)

    # Zapisz
    doc.saveas(dxf_path, encoding='utf-8')
    
    # Zakończ debugowanie
    _debug_file = None  # Reset debug file
    
    return dxf_path

# -----------------------------------------------------------------------------
# Eksport DXF dla obszarów ----------------------------------------------------
# -----------------------------------------------------------------------------

def all_collections_recursive(parent):
    """Zwraca generator wszystkich kolekcji zagnieżdżonych w parent (włącznie z parent)."""
    yield parent
    for child in parent.children:
        yield from all_collections_recursive(child)

def debug_log(message):
    """Zapisuje komunikaty debugowania do pliku txt"""
    import os
    import datetime
    
    # Ścieżka do pliku debug na Desktop
    debug_file = "/Users/michalmalewczyk/Desktop/miix_debug.txt"
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    
    # Również wypisz do konsoli
    print(f"[DEBUG] {message}")

def debug_contours_log(message):
    """Zapisuje komunikaty debugowania warstwic do osobnego pliku"""
    import os
    import datetime
    
    # Ścieżka do pliku debug warstwic na Desktop
    debug_file = "/Users/michalmalewczyk/Desktop/warstwice_debug.txt"
    
    timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    with open(debug_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    
    # Również wypisz do konsoli
    print(f"[CONTOURS] {message}")

def temporarily_disable_handlers():
    """Tymczasowo wyłącza handlery podczas eksportu"""
    disabled_handlers = []
    
    # Lista handlerów do wyłączenia
    handlers_to_disable = [
        'update_etykieta_rectangles',
        'update_ogrod_deszczowy_properties', 
        'auto_create_etykieta_mesh_objects',
        'auto_create_ogrod_deszczowy_labels',
        'update_ogrod_deszczowy_labels',
        'secure_opis_poziom_positions',
        'update_poziom_texts',
        'update_rzedna_texts',
        'update_spadek_texts',
        'auto_create_opis_spadek_text_objects',
        'update_surface_text_objects',
        'update_lokal_summary_text_objects'
    ]
    
    # Usuń handlery z depsgraph_update_post
    for handler in bpy.app.handlers.depsgraph_update_post[:]:
        if hasattr(handler, '__name__') and handler.__name__ in handlers_to_disable:
            bpy.app.handlers.depsgraph_update_post.remove(handler)
            disabled_handlers.append(('post', handler))
            print(f"[DEBUG] Wyłączono handler: {handler.__name__}")
    
    # Usuń handlery z depsgraph_update_pre
    for handler in bpy.app.handlers.depsgraph_update_pre[:]:
        if hasattr(handler, '__name__') and handler.__name__ in handlers_to_disable:
            bpy.app.handlers.depsgraph_update_pre.remove(handler)
            disabled_handlers.append(('pre', handler))
            print(f"[DEBUG] Wyłączono handler: {handler.__name__}")
    
    return disabled_handlers

def restore_handlers(disabled_handlers):
    """Przywraca wyłączone handlery"""
    for handler_type, handler in disabled_handlers:
        if handler_type == 'post':
            bpy.app.handlers.depsgraph_update_post.append(handler)
        else:
            bpy.app.handlers.depsgraph_update_pre.append(handler)
        print(f"[DEBUG] Przywrócono handler: {handler.__name__}")

def export_obszar_dxf_new(ctx):
    """Nowa funkcja eksportu DXF z Z-order i per-object properties"""
    if ezdxf is None:
        raise RuntimeError("ezdxf not installed (pip install ezdxf)")

    # Wyczyść poprzedni log i rozpocznij nowy
    import os
    debug_file = "/Users/michalmalewczyk/Desktop/miix_debug.txt"
    if os.path.exists(debug_file):
        os.remove(debug_file)
    
    debug_log("=== ROZPOCZYNAM NOWY EKSPORT DXF Z Z-ORDER ===")
    
    # Pobierz wszystkie widoczne obiekty MESH i FONT
    visible_objects = []
    for obj in bpy.data.objects:
        try:
            if obj and obj.visible_get() and obj.type in ['MESH', 'FONT']:
                visible_objects.append(obj)
                debug_log(f"Dodano obiekt: {obj.name} ({obj.type}) Z={obj.location.z:.3f}")
        except (AttributeError, ReferenceError, RuntimeError) as e:
            debug_log(f"Pominięto obiekt z powodu błędu: {e}")
            continue
    
    debug_log(f"Znaleziono {len(visible_objects)} widocznych obiektów MESH/FONT")
    
    # Sortowanie Z-order: najpierw #Opis* obiekty (od najwyższego Z), potem pozostałe (od najwyższego Z)
    def sort_key(obj):
        is_opis = obj.name.startswith("#Opis")
        z_coord = obj.location.z
        # #Opis* obiekty mają priorytet (0), pozostałe (1)
        # W każdej grupie sortuj od najwyższego Z (odwrócona kolejność)
        return (0 if is_opis else 1, -z_coord)
    
    sorted_objects = sorted(visible_objects, key=sort_key)
    debug_log(f"Posortowano obiekty wg Z-order:")
    for i, obj in enumerate(sorted_objects):
        debug_log(f"  {i+1}. {obj.name} Z={obj.location.z:.3f} {'(#Opis*)' if obj.name.startswith('#Opis') else ''}")

    # Ustawienia DXF
    directory = os.path.dirname(bpy.path.abspath(ctx.scene.render.filepath)) or bpy.path.abspath('//') or os.getcwd()
    dxf_path = os.path.join(directory, f"{ctx.view_layer.name}.dxf")
    doc = ezdxf.new(setup=True)
    doc.header["$LTSCALE"] = 0.5
    msp = doc.modelspace()

    # Twórz typy linii
    def create_linetype(name, pattern, description):
        if name not in doc.linetypes:
            doc.linetypes.new(name, dxfattribs={"pattern": pattern, "description": description})
    
    create_linetype("FENCELINE1", [2.5, -1.25, 2.5, -1.25, 0, -1.25], "Fence line 1")
    create_linetype("FENCELINE2", [2.5, -1.25, 2.5, -1.25, 2.5, -1.25], "Fence line 2")
    create_linetype("KONDYGNACJE", [4.0, -1.0, 1.0, -1.0], "Linia dla kondygnacji nadziemnych")
    create_linetype("DASHED2", [2.5, -1.25], "Dashed line 2")
    create_linetype("DASHEDX2", [5.0, -2.5], "Dashed line X2")
    create_linetype("DASHDOT2", [2.5, -1.25, 0.5, -1.25], "Dash dot line 2")
    create_linetype("DOTTED", [0.5, -0.5], "Dotted line")
    
    # Twórz warstwy z ustawień sceny (jeśli są) lub z domyślnych OBSZARY_LAYERS
    def create_dxf_layers():
        scene_layers = ctx.scene.miixarch_dxf_layers
        if len(scene_layers) > 0:
            # Użyj warstw z ustawień sceny
            debug_log(f"Używam {len(scene_layers)} warstw z ustawień sceny")
            for layer_prop in scene_layers:
                line_color = layer_prop.line_color_index if layer_prop.line_color_type == 'INDEX' else layer_prop.line_color_rgb
                _add_obszar_layer(doc, layer_prop.name, line_color, layer_prop.line_weight, None)
        else:
            # Fallback do domyślnych warstw OBSZARY_LAYERS
            debug_log("Używam domyślnych warstw z OBSZARY_LAYERS")
    for layer_name, layer_cfg in OBSZARY_LAYERS.items():
        _add_obszar_layer(doc, layer_cfg["layer"], layer_cfg.get("color", 7), 
                         layer_cfg.get("weight", 13), layer_cfg.get("linetype"))

    create_dxf_layers()
    
    # Funkcje pomocnicze dla per-object properties
    def get_layer_properties(obj):
        """Pobiera właściwości warstwy dla obiektu"""
        layer_name = get_object_dxf_layer(obj)
        if layer_name:
            # Znajdź warstwę z ustawień sceny po nazwie
            scene_layers = ctx.scene.miixarch_dxf_layers
            for layer in scene_layers:
                if layer.name == layer_name:
                    return layer
        
        # Fallback - znajdź warstwę z OBSZARY_LAYERS na podstawie nazwy/kolekcji
        return get_fallback_layer_properties(obj)
    
    def get_fallback_layer_properties(obj):
        """Fallback do automatycznego określania warstwy na podstawie nazwy/kolekcji"""
        obszar_type = get_obszar_type_from_object_name(obj.name)
        if not obszar_type and obj.users_collection:
            obszar_type = get_obszar_type_from_collection(obj.users_collection[0].name)
        
        if obszar_type and obszar_type in OBSZARY_LAYERS:
            layer_cfg = OBSZARY_LAYERS[obszar_type]
            # Zwróć dane w formacie podobnym do MIIXARCH_LayerProperty
            class FallbackLayer:
                def __init__(self, cfg):
                    self.name = cfg.get("layer", "0")
                    self.line_color_type = 'RGB' if isinstance(cfg.get("color"), tuple) else 'INDEX'
                    self.line_color_index = cfg.get("color", 7) if not isinstance(cfg.get("color"), tuple) else 7
                    self.line_color_rgb = tuple(c/255.0 for c in cfg.get("color", (255,255,255))) if isinstance(cfg.get("color"), tuple) else (1,1,1)
                    self.hatch_color_type = self.line_color_type
                    self.hatch_color_index = self.line_color_index
                    self.hatch_color_rgb = self.line_color_rgb
                    self.line_weight = cfg.get("weight", 13)
                    self.hatch_pattern = cfg.get("hatch_pattern", "SOLID")
                    self.hatch_scale = cfg.get("hatch_scale", 1.0)
                    self.hatch_rotation = cfg.get("hatch_rotation", 0.0)
            return FallbackLayer(layer_cfg)
        
        # Domyślna warstwa
        class DefaultLayer:
            name = "0"
            line_color_type = 'INDEX'
            line_color_index = 7
            line_color_rgb = (1,1,1)
            hatch_color_type = 'INDEX'
            hatch_color_index = 7
            hatch_color_rgb = (1,1,1)
            line_weight = 13
            hatch_pattern = "SOLID"
            hatch_scale = 1.0
            hatch_rotation = 0.0
        return DefaultLayer()

    SCALE = 1.0  # Bez skalowania dla obszarów
    
    # Funkcje eksportu dla różnych typów obiektów
    def export_mesh_object(obj, layer_props, msp, doc, ctx, export_mode='both'):
        """Eksportuje obiekt MESH z użyciem per-object properties
        export_mode: 'hatches', 'edges', 'both'
        """
        # Pobierz ustawienia z Custom Properties
        export_hatches = get_object_hatches(obj)
        export_boundary_edges = get_object_boundary_edges(obj)
        export_internal_edges = get_object_internal_edges(obj)
        
        # Sprawdź cache
        cached_data = get_cached_geometry(obj)
        
        if cached_data:
            debug_log(f"  Używam cached mesh dla {obj.name}")
        else:
            debug_log(f"  Przetwarzam mesh dla {obj.name} (brak cache lub zmieniony)")
        
        # Zawsze twórz mesh - cache zostanie zaimplementowany później
        deps = ctx.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(deps)
        try:
            mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps)
        except Exception as e:
            debug_log(f"  Błąd tworzenia mesh dla {obj.name}: {e}")
            return
            
        try:
            # Eksportuj hatches (jeśli włączone i w odpowiednim trybie)
            if (export_mode in ['hatches', 'both']) and export_hatches and mesh.polygons:
                debug_log(f"  Eksportuję {len(mesh.polygons)} hatches")
                for poly in mesh.polygons:
                    pts = [obj.matrix_world @ mesh.vertices[i].co for i in poly.vertices]
                    poly2d = [(p.x * SCALE, p.y * SCALE) for p in pts]
                    
                    hatch = msp.add_hatch(dxfattribs={"layer": layer_props.name})
                    hatch.paths.add_polyline_path(poly2d, is_closed=True)
                    
                    # Ustawienia hatchu z właściwości warstwy
                    if layer_props.hatch_pattern == "SOLID":
                        hatch.set_solid_fill()
                    else:
                        hatch.set_pattern_fill(layer_props.hatch_pattern, 
                         scale=layer_props.hatch_scale,
                         angle=layer_props.hatch_rotation)
                    
                    # Kolor hatchu
                    if layer_props.hatch_color_type == 'RGB':
                        hatch.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in layer_props.hatch_color_rgb])
                    elif layer_props.hatch_color_type == 'PRONEKO':
                        proneko_rgb = get_proneko_color_rgb(layer_props.hatch_color_proneko)
                        hatch.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in proneko_rgb])
                    else:
                        hatch.dxf.color = layer_props.hatch_color_index
            
            # Eksportuj krawędzie (jeśli w odpowiednim trybie)
            if export_mode in ['edges', 'both']:
                mesh.calc_loop_triangles()
                
                # Krawędzie brzegowe
                if export_boundary_edges:
                    debug_log(f"  Eksportuję krawędzie brzegowe")
                    for edge in mesh.edges:
                        # Sprawdź czy krawędź jest brzegowa (połączona z <= 1 ścianą)
                        v1, v2 = edge.vertices
                        connected_faces = [poly for poly in mesh.polygons if v1 in poly.vertices and v2 in poly.vertices]
                        
                        if len(connected_faces) <= 1:  # Brzegowe lub wolne krawędzie
                            p1 = obj.matrix_world @ mesh.vertices[v1].co
                            p2 = obj.matrix_world @ mesh.vertices[v2].co
                            
                            line = msp.add_line(
                                (p1.x * SCALE, p1.y * SCALE),
                                (p2.x * SCALE, p2.y * SCALE),
                                dxfattribs={"layer": layer_props.name}
                            )
                            
                            # Kolor linii
                            if layer_props.line_color_type == 'RGB':
                                line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in layer_props.line_color_rgb])
                            elif layer_props.line_color_type == 'PRONEKO':
                                proneko_rgb = get_proneko_color_rgb(layer_props.line_color_proneko)
                                line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in proneko_rgb])
                
                # Krawędzie wewnętrzne
                if export_internal_edges:
                    debug_log(f"  Eksportuję krawędzie wewnętrzne")
                    for edge in mesh.edges:
                        # Sprawdź czy krawędź jest wewnętrzna (połączona z > 1 ścianą)
                        v1, v2 = edge.vertices
                        connected_faces = [poly for poly in mesh.polygons if v1 in poly.vertices and v2 in poly.vertices]
                        
                        if len(connected_faces) > 1:  # Krawędzie wewnętrzne
                            p1 = obj.matrix_world @ mesh.vertices[v1].co
                            p2 = obj.matrix_world @ mesh.vertices[v2].co
                            
                            line = msp.add_line(
                                (p1.x * SCALE, p1.y * SCALE),
                                (p2.x * SCALE, p2.y * SCALE),
                                dxfattribs={"layer": layer_props.name}
                            )
                        if layer_props.line_color_type == 'RGB':
                            line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in layer_props.line_color_rgb])
                        elif layer_props.line_color_type == 'PRONEKO':
                            proneko_rgb = get_proneko_color_rgb(layer_props.line_color_proneko)
                            line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in proneko_rgb])
                        else:
                            line.dxf.color = layer_props.line_color_index
        
        except Exception as e:
            debug_log(f"  Błąd eksportu mesh {obj.name}: {e}")
        finally:
            if mesh:
                # Zapisz do cache przed usunięciem mesh
                if not cached_data:
                    debug_log(f"  Zapisuję mesh {obj.name} do cache")
                    geometry_data = {
                        'vertices': [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices],
                        'edges': [(e.vertices[0], e.vertices[1]) for e in mesh.edges],
                        'polygons': [list(p.vertices) for p in mesh.polygons],
                        'export_type': 'mesh'
                    }
                    cache_object_geometry(obj, geometry_data)
                
                bpy.data.meshes.remove(mesh)
                
    def export_font_object(obj, layer_props, msp, doc, ctx, export_mode='both'):
        """Eksportuje obiekt FONT jako mesh krawędzie (zachowuje formatowanie)
        export_mode: 'hatches', 'edges', 'both'
        """
        
        # DIAGNOSTYKA: sprawdź podstawowe właściwości obiektu font
        debug_log(f"  Font {obj.name}: data.body='{getattr(obj.data, 'body', 'BRAK')}', visible={obj.visible_get()}")
        
        # Sprawdź cache dla fontów
        cached_data = get_cached_geometry(obj)
        
        if cached_data:
            debug_log(f"  Używam cached font mesh dla {obj.name}")
        else:
            debug_log(f"  Przetwarzam font {obj.name} (brak cache lub zmieniony)")
        
        # OPTYMALIZACJA: Obniż resolution_u dla przyspieszenia eksportu
        original_resolution_u = None
        if hasattr(obj.data, 'resolution_u'):
            original_resolution_u = obj.data.resolution_u
            obj.data.resolution_u = 2
            debug_log(f"  Font {obj.name}: resolution_u zmieniona z {original_resolution_u} na 2")
        
        # WYMUSZENIE AKTUALIZACJI SCENY dla poprawnej konwersji
        try:
            bpy.context.view_layer.update()
        except:
            pass
        
        # KONWERSJA DO MESH z zachowaniem formatowania
        try:
            # Pobierz evaluated object z dependency graph
            deps = ctx.evaluated_depsgraph_get()
            eval_obj = obj.evaluated_get(deps)
            
            # Sprawdź czy obiekt ma geometrię
            if eval_obj is None:
                debug_log(f"  Font {obj.name}: brak evaluated object")
                return
            
            # Konwertuj do mesh
            mesh = bpy.data.meshes.new_from_object(eval_obj, depsgraph=deps)
            
            debug_log(f"  Font {obj.name} → mesh: {len(mesh.vertices)} vertices, {len(mesh.edges)} edges, {len(mesh.polygons)} polygons")
            
            # Sprawdź czy mamy jakąkolwiek geometrię
            if len(mesh.vertices) == 0:
                debug_log(f"  Font {obj.name}: brak vertices - sprawdzam alternatywne metody")
                bpy.data.meshes.remove(mesh)
                
                # ALTERNATYWNA METODA: Spróbuj convert to mesh w kontekście
                try:
                    # Duplikuj obiekt tymczasowo dla konwersji
                    temp_obj = obj.copy()
                    temp_obj.data = obj.data.copy()
                    
                    # Dodaj do sceny tymczasowo
                    bpy.context.collection.objects.link(temp_obj)
                    bpy.context.view_layer.update()
                    
                    # Konwertuj używając modifiers
                    temp_obj.select_set(True)
                    bpy.context.view_layer.objects.active = temp_obj
                    
                    # Spróbuj konwersji
                    deps2 = bpy.context.evaluated_depsgraph_get()
                    eval_temp = temp_obj.evaluated_get(deps2)
                    mesh2 = bpy.data.meshes.new_from_object(eval_temp, depsgraph=deps2)
                    
                    debug_log(f"  Font {obj.name} → mesh2: {len(mesh2.vertices)} vertices, {len(mesh2.edges)} edges, {len(mesh2.polygons)} polygons")
                    
                    # Usuń tymczasowy obiekt
                    bpy.context.collection.objects.unlink(temp_obj)
                    bpy.data.objects.remove(temp_obj)
                    
                    if len(mesh2.vertices) > 0:
                        mesh = mesh2
                    else:
                        bpy.data.meshes.remove(mesh2)
                        debug_log(f"  Font {obj.name}: nie udało się wygenerować geometrii")
                        return
                                                                        
                except Exception as e:
                    debug_log(f"  Font {obj.name}: błąd alternatywnej konwersji: {e}")
                    return
            
            if len(mesh.vertices) == 0:
                debug_log(f"  Font {obj.name}: nadal brak geometrii - pomijam")
                bpy.data.meshes.remove(mesh)
                return
            
            # EKSPORTUJ WSZYST­KIE KRAWĘDZIE (dla zachowania pełnego wyglądu tekstu)
            if export_mode in ['edges', 'both']:
                debug_log(f"  Eksportuję font {obj.name} jako {len(mesh.edges)} krawędzi")
                
                # Dla fontów eksportujemy WSZYSTKIE krawędzie, nie tylko brzegowe
                for edge in mesh.edges:
                    v1, v2 = edge.vertices
                    p1 = obj.matrix_world @ mesh.vertices[v1].co
                    p2 = obj.matrix_world @ mesh.vertices[v2].co
                    
                    line = msp.add_line(
                        (p1.x * SCALE, p1.y * SCALE),
                        (p2.x * SCALE, p2.y * SCALE),
                        dxfattribs={"layer": layer_props.name}
                    )
                    
                    # Kolor krawędzi
                    if layer_props.line_color_type == 'RGB':
                        line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in layer_props.line_color_rgb])
                    elif layer_props.line_color_type == 'PRONEKO':
                        proneko_rgb = get_proneko_color_rgb(layer_props.line_color_proneko)
                        line.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in proneko_rgb])
                    else:
                        line.dxf.color = layer_props.line_color_index
                
                debug_log(f"  Font {obj.name}: wyeksportowano {len(mesh.edges)} krawędzi")
            
            # EKSPORTUJ HATCHES (opcjonalnie dla wypełnień)
            if export_mode in ['hatches', 'both'] and len(mesh.polygons) > 0:
                debug_log(f"  Eksportuję font {obj.name} jako {len(mesh.polygons)} hatches")
                
                for poly in mesh.polygons:
                    pts = [obj.matrix_world @ mesh.vertices[i].co for i in poly.vertices]
                    poly2d = [(p.x * SCALE, p.y * SCALE) for p in pts]
                    
                    hatch = msp.add_hatch(dxfattribs={"layer": layer_props.name})
                    hatch.paths.add_polyline_path(poly2d, is_closed=True)
                    hatch.set_solid_fill()
                    
                    # Kolor hatchu
                    if layer_props.hatch_color_type == 'RGB':
                        hatch.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in layer_props.hatch_color_rgb])
                    elif layer_props.hatch_color_type == 'PRONEKO':
                        proneko_rgb = get_proneko_color_rgb(layer_props.hatch_color_proneko)
                        hatch.dxf.true_color = rgb_to_truecolor_int([int(c*255) for c in proneko_rgb])
                    else:
                        hatch.dxf.color = layer_props.hatch_color_index
                    
            # Zapisz do cache przed usunięciem mesh
            if not cached_data:
                debug_log(f"  Zapisuję font {obj.name} do cache")
                geometry_data = {
                    'vertices': [(v.co.x, v.co.y, v.co.z) for v in mesh.vertices],
                    'edges': [(e.vertices[0], e.vertices[1]) for e in mesh.edges],
                    'polygons': [list(p.vertices) for p in mesh.polygons],
                    'export_type': 'font',
                    'font_body': getattr(obj.data, 'body', '')
                }
                cache_object_geometry(obj, geometry_data)
            
                bpy.data.meshes.remove(mesh)
            
        except Exception as e:
            debug_log(f"  Błąd eksportu font {obj.name}: {e}")
        
        finally:
            # PRZYWRÓĆ ORYGINALNĄ RESOLUTION_U
            if original_resolution_u is not None and hasattr(obj.data, 'resolution_u'):
                obj.data.resolution_u = original_resolution_u
                debug_log(f"  Font {obj.name}: resolution_u przywrócona do {original_resolution_u}")

    # GŁÓWNA PĘTLA EKSPORTU - 4-przepustowy system
    debug_log("=== ROZPOCZYNAM 4-PRZEPUSTOWY EKSPORT ===")
    
    # Podziel obiekty na grupy: z "#Opis" i bez "#Opis"
    non_opis_objects = []
    opis_objects = []
    
    for obj in sorted_objects:
        if "#Opis" in obj.name:
            opis_objects.append(obj)
        else:
            non_opis_objects.append(obj)
    
    debug_log(f"Obiekty bez '#Opis': {len(non_opis_objects)}")
    debug_log(f"Obiekty z '#Opis': {len(opis_objects)}")
    
    exported_count = 0
    
    # PASS 1: Hatches obiektów bez "#Opis" (Z-order: wysokie → niskie)
    debug_log("=== PASS 1: HATCHES obiektów bez '#Opis' ===")
    for obj in non_opis_objects:
        try:
            debug_log(f"PASS 1 - Hatches: {obj.name} ({obj.type}) Z={obj.location.z:.3f}")
            layer_props = get_layer_properties(obj)
            
            if obj.type == 'MESH':
                export_mesh_object(obj, layer_props, msp, doc, ctx, export_mode='hatches')
            elif obj.type == 'FONT':
                export_font_object(obj, layer_props, msp, doc, ctx, export_mode='hatches')
            
            exported_count += 1
            
        except Exception as e:
            debug_log(f"PASS 1 błąd eksportu {obj.name}: {e}")
            continue
    
    # PASS 2: Edges obiektów bez "#Opis" (Z-order: wysokie → niskie)
    debug_log("=== PASS 2: EDGES obiektów bez '#Opis' ===")
    for obj in non_opis_objects:
        try:
            debug_log(f"PASS 2 - Edges: {obj.name} ({obj.type}) Z={obj.location.z:.3f}")
            layer_props = get_layer_properties(obj)
            
            if obj.type == 'MESH':
                export_mesh_object(obj, layer_props, msp, doc, ctx, export_mode='edges')
            elif obj.type == 'FONT':
                export_font_object(obj, layer_props, msp, doc, ctx, export_mode='edges')
            
        except Exception as e:
            debug_log(f"PASS 2 błąd eksportu {obj.name}: {e}")
            continue
    
    # PASS 3: Hatches obiektów z "#Opis" (Z-order: wysokie → niskie)
    debug_log("=== PASS 3: HATCHES obiektów z '#Opis' ===")
    for obj in opis_objects:
        try:
            debug_log(f"PASS 3 - Hatches: {obj.name} ({obj.type}) Z={obj.location.z:.3f}")
            layer_props = get_layer_properties(obj)
            
            if obj.type == 'MESH':
                export_mesh_object(obj, layer_props, msp, doc, ctx, export_mode='hatches')
            elif obj.type == 'FONT':
                export_font_object(obj, layer_props, msp, doc, ctx, export_mode='hatches')
            
        except Exception as e:
            debug_log(f"PASS 3 błąd eksportu {obj.name}: {e}")
            continue
    
    # PASS 4: Edges obiektów z "#Opis" (Z-order: wysokie → niskie)
    debug_log("=== PASS 4: EDGES obiektów z '#Opis' ===")
    for obj in opis_objects:
        try:
            debug_log(f"PASS 4 - Edges: {obj.name} ({obj.type}) Z={obj.location.z:.3f}")
            layer_props = get_layer_properties(obj)
            
            if obj.type == 'MESH':
                export_mesh_object(obj, layer_props, msp, doc, ctx, export_mode='edges')
            elif obj.type == 'FONT':
                export_font_object(obj, layer_props, msp, doc, ctx, export_mode='edges')
            
        except Exception as e:
            debug_log(f"PASS 4 błąd eksportu {obj.name}: {e}")
            continue
    
    debug_log(f"=== 4-PRZEPUSTOWY EKSPORT ZAKOŃCZONY: {exported_count}/{len(sorted_objects)} obiektów ===")
    
    # Zapisz plik DXF
    try:
        doc.saveas(dxf_path)
        debug_log(f"Plik DXF zapisany: {dxf_path}")
        return {'FINISHED'}
    except Exception as e:
        debug_log(f"Błąd zapisu pliku DXF: {e}")
        raise RuntimeError(f"Nie udało się zapisać pliku DXF: {e}")



# OBSZARY_LAYERS dictionary with new hatch properties

class MIIXARCH_OT_AddLayer(Operator):
    bl_idname = "miixarch.add_layer"
    bl_label = "Dodaj warstwę"
    bl_description = "Dodaje nową warstwę DXF"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        new_layer = scene.miixarch_dxf_layers.add()
        new_layer.name = f"NOWA_WARSTWA_{len(scene.miixarch_dxf_layers)}"
        return {'FINISHED'}

class MIIXARCH_OT_RemoveLayer(Operator):
    bl_idname = "miixarch.remove_layer"
    bl_label = "Usuń warstwę"
    bl_description = "Usuwa zaznaczoną warstwę DXF"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: IntProperty()
    
    def execute(self, context):
        scene = context.scene
        if 0 <= self.index < len(scene.miixarch_dxf_layers):
            scene.miixarch_dxf_layers.remove(self.index)
        return {'FINISHED'}

class MIIXARCH_OT_InitializeDefaultLayers(Operator):
    bl_idname = "miixarch.initialize_default_layers"
    bl_label = "Zainicjuj domyślne warstwy"
    bl_description = "Tworzy domyślne warstwy z OBSZARY_LAYERS"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        scene.miixarch_dxf_layers.clear()
    
        # Sortuj alfabetycznie
        sorted_layers = sorted(OBSZARY_LAYERS.items())
        
        for layer_key, layer_data in sorted_layers:
            new_layer = scene.miixarch_dxf_layers.add()
            new_layer.name = layer_data.get("layer", layer_key)
            
            # Konwertuj kolor
            color = layer_data.get("color", 7)
            if isinstance(color, tuple):
                new_layer.line_color_type = 'RGB'
                new_layer.line_color_rgb = (color[0]/255.0, color[1]/255.0, color[2]/255.0)
                new_layer.hatch_color_type = 'RGB'
                new_layer.hatch_color_rgb = (color[0]/255.0, color[1]/255.0, color[2]/255.0)
            else:
                new_layer.line_color_type = 'INDEX'
                new_layer.line_color_index = color
                new_layer.hatch_color_type = 'INDEX'
                new_layer.hatch_color_index = color
            
            # Pozostałe właściwości
            new_layer.line_weight = layer_data.get("weight", 13)
            new_layer.line_scale = 1.0
            new_layer.hatch_weight = layer_data.get("weight", 13)
            new_layer.hatch_pattern = layer_data.get("hatch_pattern", "SOLID")
            new_layer.hatch_scale = layer_data.get("hatch_scale", 1.0)
            new_layer.hatch_rotation = layer_data.get("hatch_rotation", 0.0)
            
            # Specjalne kolory hatchu
            hatch_rgb = layer_data.get("hatch_rgb")
            if hatch_rgb:
                new_layer.hatch_color_type = 'RGB'
                new_layer.hatch_color_rgb = (hatch_rgb[0]/255.0, hatch_rgb[1]/255.0, hatch_rgb[2]/255.0)
        
        self.report({'INFO'}, f"Zainicjowano {len(scene.miixarch_dxf_layers)} warstw")
        
        # Automatycznie eksportuj warstwy do Text bloku
        auto_export_layers_to_text()
        
        return {'FINISHED'}

class MIIXARCH_OT_ExpandAllLayers(Operator):
    bl_idname = "miixarch.expand_all_layers"
    bl_label = "Rozwiń wszystkie warstwy"
    bl_description = "Rozwija wszystkie warstwy w panelu"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        for layer in scene.miixarch_dxf_layers:
            layer.expanded = True
        return {'FINISHED'}

class MIIXARCH_OT_CollapseAllLayers(Operator):
    bl_idname = "miixarch.collapse_all_layers"
    bl_label = "Zwiń wszystkie warstwy"
    bl_description = "Zwija wszystkie warstwy w panelu"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        scene = context.scene
        for layer in scene.miixarch_dxf_layers:
            layer.expanded = False
        return {'FINISHED'}

class MIIXARCH_OT_AssignDXFSettings(Operator):
    bl_idname = "miixarch.assign_dxf_settings"
    bl_label = "Przypisz ustawienia warstw"
    bl_description = "Przypisuje ustawienia DXF do zaznaczonych obiektów"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        selected_objects = context.selected_objects
        scene = context.scene
        
        if not selected_objects:
            self.report({'ERROR'}, "Brak zaznaczonych obiektów")
            return {'CANCELLED'}
        
        # Filtruj tylko MESH i FONT obiekty
        valid_objects = [obj for obj in selected_objects if obj.type in ['MESH', 'FONT']]
        
        if not valid_objects:
            self.report({'ERROR'}, "Żaden z zaznaczonych obiektów nie jest typu MESH lub FONT")
            return {'CANCELLED'}
        
        # Pobierz ustawienia z UI
        layer_name = scene.miixarch_selected_layer
        boundary_edges = scene.miixarch_ui_boundary_edges
        internal_edges = scene.miixarch_ui_internal_edges
        hatches = scene.miixarch_ui_hatches
        
        # Przypisz ustawienia do wszystkich odpowiednich obiektów
        processed_count = 0
        for obj in valid_objects:
            # Przypisz warstwę
            if layer_name and layer_name != 'NONE':
                set_object_dxf_layer(obj, layer_name)
            
            # Przypisz ustawienia dla MESH
            if obj.type == 'MESH':
                set_object_boundary_edges(obj, boundary_edges)
                set_object_internal_edges(obj, internal_edges)
                set_object_hatches(obj, hatches)
            
            processed_count += 1
        
        # Odśwież panel
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        layer_info = f" (warstwa: {layer_name})" if layer_name and layer_name != 'NONE' else ""
        self.report({'INFO'}, f"Ustawienia DXF przypisane do {processed_count} obiektów{layer_info}")
        return {'FINISHED'}

class MIIXARCH_OT_CopyDXFSettings(Operator):
    bl_idname = "miixarch.copy_dxf_settings"
    bl_label = "Kopiuj ustawienia warstw"
    bl_description = "Kopiuje ustawienia DXF z aktywnego obiektu do zaznaczonych obiektów"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        active_obj = context.active_object
        selected_objects = context.selected_objects
        
        if not active_obj:
            self.report({'ERROR'}, "Brak aktywnego obiektu")
            return {'CANCELLED'}
        
        if active_obj.type not in ['MESH', 'FONT']:
            self.report({'ERROR'}, "Aktywny obiekt musi być typu MESH lub FONT")
            return {'CANCELLED'}
        
        # Pobierz ustawienia z aktywnego obiektu
        source_layer = get_object_dxf_layer(active_obj)
        source_boundary = get_object_boundary_edges(active_obj)
        source_internal = get_object_internal_edges(active_obj)
        source_hatches = get_object_hatches(active_obj)
        
        # Sprawdź czy aktywny obiekt ma jakiekolwiek ustawienia DXF
        if not source_layer and source_boundary is True and source_internal is False and source_hatches is True:
            self.report({'WARNING'}, "Aktywny obiekt nie ma niestandardowych ustawień DXF")
        
        # Kopiuj ustawienia do zaznaczonych obiektów (z wyjątkiem aktywnego)
        copied_count = 0
        for obj in selected_objects:
            if obj != active_obj and obj.type in ['MESH', 'FONT']:
                # Kopiuj warstwę
                if source_layer:
                    set_object_dxf_layer(obj, source_layer)
                
                # Kopiuj ustawienia dla MESH
                if obj.type == 'MESH':
                    set_object_boundary_edges(obj, source_boundary)
                    set_object_internal_edges(obj, source_internal)
                    set_object_hatches(obj, source_hatches)
                
                copied_count += 1
        
        if copied_count == 0:
            self.report({'WARNING'}, "Brak odpowiednich obiektów do kopiowania (MESH lub FONT)")
        else:
            # Odśwież viewport
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            
            layer_info = f" (warstwa: {source_layer})" if source_layer else ""
            self.report({'INFO'}, f"Skopiowano ustawienia DXF do {copied_count} obiektów{layer_info}")
        
        return {'FINISHED'}

class MIIXARCH_OT_ExportLayersToText(Operator):
    bl_idname = "miixarch.export_layers_to_text"
    bl_label = "Eksportuj warstwy do Text"
    bl_description = "Eksportuje warstwy DXF do Text bloku w Blenderze"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        result, message = export_layers_to_text()
        if result == {'FINISHED'}:
            self.report({'INFO'}, message)
        else:
            self.report({'ERROR'}, message)
        return result

class MIIXARCH_OT_ImportLayersFromText(Operator):
    bl_idname = "miixarch.import_layers_from_text"
    bl_label = "Importuj warstwy z Text"
    bl_description = "Importuje warstwy DXF z Text bloku w Blenderze"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        result, message = import_layers_from_text()
        if result == {'FINISHED'}:
            self.report({'INFO'}, message)
            # Odśwież UI
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
        else:
            self.report({'ERROR'}, message)
        return result

class MIIXARCH_OT_ClearDXFCache(Operator):
    bl_idname = "miixarch.clear_dxf_cache"
    bl_label = "Wyczyść cache DXF"
    bl_description = "Czyści cache DXF i wymusza ponowne przetworzenie obiektów"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        global _dxf_memory_cache
        _dxf_memory_cache = {
            'version': '1.0',
            'blend_file': bpy.data.filepath,
            'last_updated': datetime.now().isoformat(),
            'objects': {}
        }
        
        # Zapisz wyczyszczony cache do Text bloku
        save_dxf_cache()
        
        self.report({'INFO'}, "Cache DXF wyczyszczony")
        return {'FINISHED'}

class MIIXARCH_OT_ShowDXFCacheStats(Operator):
    bl_idname = "miixarch.show_dxf_cache_stats"
    bl_label = "Statystyki cache DXF"
    bl_description = "Pokazuje statystyki cache DXF"
    
    def execute(self, context):
        stats = get_dxf_cache_statistics()
        
        message = f"Cache DXF: {stats['total_objects']} obiektów, {stats['cache_size_kb']:.1f} KB"
        message += f"\nLokalizacja: {stats['cache_location']}"
        
        self.report({'INFO'}, message)
        return {'FINISHED'}

class MIIXARCH_OT_SetMaterialVisibility(Operator):
    bl_idname = "miixarch.set_material_visibility"
    bl_label = "Ustaw widoczność materiału"
    bl_description = "Kontroluje widoczność obiektów według typu materiału"
    
    material_type: StringProperty()
    action: EnumProperty(
        items=[
            ('DISABLE_VIEWPORT', 'Disable in Viewport', 'Wyłącz w viewport (bpy.context)'),
            ('HIDE_VIEWPORT', 'Hide in Viewport', 'Ukryj w viewport'),
            ('HIDE_RENDER', 'Hide in Renders', 'Ukryj w renderach'),
        ]
    )
    
    def execute(self, context):
        objects = get_objects_by_material_type(self.material_type)
        
        if not objects:
            self.report({'INFO'}, f"Nie znaleziono obiektów dla: {self.material_type}")
            return {'FINISHED'}
        
        # Sprawdź obecny stan większości obiektów aby zdecydować czy włączyć czy wyłączyć
        if self.action == 'DISABLE_VIEWPORT':
            # Sprawdź ile obiektów jest wyłączonych (hide_get() == True)
            disabled_count = sum(1 for obj in objects if obj.hide_get())
            new_state = disabled_count < len(objects) / 2  # Jeśli mniej niż połowa wyłączona, wyłącz wszystkie
            for obj in objects:
                obj.hide_set(new_state)
        elif self.action == 'HIDE_VIEWPORT':
            # Sprawdź ile obiektów ma hide_viewport == True
            hidden_count = sum(1 for obj in objects if obj.hide_viewport)
            new_state = hidden_count < len(objects) / 2  # Jeśli mniej niż połowa ukryta, ukryj wszystkie
            for obj in objects:
                obj.hide_viewport = new_state
        elif self.action == 'HIDE_RENDER':
            # Sprawdź ile obiektów ma hide_render == True
            hidden_count = sum(1 for obj in objects if obj.hide_render)
            new_state = hidden_count < len(objects) / 2  # Jeśli mniej niż połowa ukryta, ukryj wszystkie
            for obj in objects:
                obj.hide_render = new_state
        
        # Odśwież viewport
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        
        action_names = {
            'DISABLE_VIEWPORT': 'aktywność w viewport (bpy.context)',
            'HIDE_VIEWPORT': 'widoczność w viewport', 
            'HIDE_RENDER': 'widoczność w renderach'
        }
        
        state_names = {True: 'wyłączono', False: 'włączono'}
        state_word = state_names.get(new_state, 'zmieniono')
        
        self.report({'INFO'}, f"{state_word.capitalize()} {action_names[self.action]} dla {len(objects)} obiektów: {self.material_type}")
        return {'FINISHED'}

class MIIX_OT_export_drawing_layers(bpy.types.Operator):
    bl_idname = "miix.export_drawing_layers"
    bl_label  = "Rysunek CAD - rzut"

    def execute(self, context):
        global _log_file
        import time
        start_time = time.time()
        
        # Sprawdź płaszczyznę cięcia
        plane = get_cutting_plane(context)
        if plane is None:
            self.report({'ERROR'}, "Brak aktywnej kamery")
            return {'CANCELLED'}
        
        cam, origin, normal = plane
        
        # Znajdź kolekcję o nazwie kamery
        camera_coll_name = cam.name
        coll = bpy.data.collections.get(camera_coll_name)
        
        if coll is None:
            self.report({'ERROR'}, f"Brak kolekcji '{camera_coll_name}'. Użyj najpierw 'Aktualizuj rysunek'")
            return {'CANCELLED'}
        
        # Inicjalizuj logowanie
            directory = os.path.dirname(bpy.path.abspath(context.scene.render.filepath)) or bpy.path.abspath('//') or os.getcwd()
            log_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        global _log_file
        # _log_file = os.path.join(directory, f"export_{cam.name}_{log_time}.txt")  # Logowanie dezaktywowane
            
        
        # Sprawdź czy są jakieś obiekty do eksportu
        if not coll.objects:
            self.report({'WARNING'}, f"Kolekcja '{camera_coll_name}' jest pusta. Użyj najpierw 'Aktualizuj rysunek'")
            return {'CANCELLED'}
        
        # Eksportuj do DXF bezpośrednio z kolekcji
        try:
            path = export_dxf(context, coll)
        except Exception as e:
            self.report({'ERROR'}, f"Błąd eksportu DXF: {e}")
            return {'CANCELLED'}
        
        # Raport końcowy
        elapsed_time = time.time() - start_time
        success_msg = f"Eksport w {elapsed_time:.1f}s z kolekcji '{camera_coll_name}'"
        
        
        # Automatyczne czyszczenie cache po eksporcie
        clear_bmesh_cache()
        
        self.report({'INFO'}, f"{success_msg}. Zapisano: {path}")
        
        return {'FINISHED'}

class MIIX_OT_export_obszar_drawing(bpy.types.Operator):
    bl_idname = "miix.export_obszar_drawing"
    bl_label  = "Rysunek CAD - plansza podstawowa"

    def execute(self, context):
        try:
            print("[DEBUG] Rozpoczynam eksport DXF...")
            path = export_obszar_dxf_new(context)  # Używam nowej funkcji eksportu
            print(f"[DEBUG] Eksport zakończony pomyślnie: {path}")
        except (AttributeError, ReferenceError, RuntimeError) as e:
            error_msg = str(e)
            print(f"[DEBUG] Błąd eksportu (StructRNA): {error_msg}")
            if "StructRNA" in error_msg and "removed" in error_msg:
                self.report({'ERROR'}, f"Błąd eksportu: obiekt został usunięty z pamięci podczas eksportu. Szczegóły: {error_msg}")
            else:
                self.report({'ERROR'}, f"DXF error: {error_msg}")
            return {'CANCELLED'}
        except Exception as e:
            print(f"[DEBUG] Nieoczekiwany błąd eksportu: {e}")
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f"DXF error: {e}")
            return {'CANCELLED'}
        
        # Automatyczne czyszczenie cache po eksporcie
        clear_bmesh_cache()
        
        self.report({'INFO'}, f"Zapisano: {path}")
        return {'FINISHED'}

# Dodaj brakujące operatory i panele

class MIIXARCH_OT_AssignSurface(Operator):
    bl_idname = "miixarch.assign_surface"
    bl_label = "Przypisz Powierzchnię"

    surface_type: EnumProperty(
        name="Rodzaj",
        description="Wybierz rodzaj powierzchni",
        items=surface_types
    )

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type in {'MESH', 'CURVE'}:
                new_name = f"#{self.surface_type.replace('_', '-')}"
                obj.name = new_name
                if self.surface_type in [
                    'Powierzchnia_netto_uzytkowa',
                    'Powierzchnia_netto_wewnetrzna',
                    'Powierzchnia_brutto_calkowita',
                    'Powierzchnia_brutto_zabudowy',
                ]:
                    area = calculate_area(obj)
                    obj["Powierzchnia"] = area
        return {'FINISHED'}

class MIIXARCH_OT_AssignObjectType(Operator):
    bl_idname = "miixarch.assign_object_type"
    bl_label = "Przypisz typ obiektu"

    object_type: EnumProperty(
        name="Typ obiektu",
        description="Wybierz typ obiektu",
        items=get_object_type_items
    )

    def execute(self, context):
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                base_name = self.object_type
                # Znajdź wolny suffix
                idx = 1
                new_name = f"{base_name}.001"
                while new_name in bpy.data.objects:
                    idx += 1
                    new_name = f"{base_name}.{str(idx).zfill(3)}"
                obj.name = new_name
                # Usuń wszystkie custom property
                for k in list(obj.keys()):
                    if not k.startswith("_"):
                        del obj[k]
                # Przypisz custom property
                if base_name in ["#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy"]:
                    # Użyj nowej funkcji z obsługą OSTAB
                    area_data = calculate_area_xy_with_ostab(obj)
                    
                    # Ustaw custom properties
                    for prop_name, value in area_data.items():
                        obj[prop_name] = value
                elif base_name == "#Ogród_deszczowy":
                    # Oblicz powierzchnię największego face
                    largest_face_area = calculate_largest_face_area_xy(obj)
                    volume = calculate_volume(obj)
                    depth = calculate_depth(obj)
                    obj["Powierzchnia"] = round(largest_face_area, 2)
                    obj["Objętość"] = round(volume, 4)
                    obj["Głębokość"] = round(depth, 2)
        return {'FINISHED'}

class MIIXARCH_OT_GenerateContours(Operator):
    bl_idname = "miixarch.generate_contours"
    bl_label = "Generuj warstwice"
    bl_description = "Generuje warstwice dla zaznaczonych obiektów"
    bl_options = {'REGISTER', 'UNDO'}

    interval: FloatProperty(
        name="Interwał warstwic",
        description="Odstęp między poszczególnymi warstwicami",
        default=1.0,
        min=0.01,
        max=100.0,
        precision=2
    )

    def invoke(self, context, event):
        # Sprawdź czy są zaznaczone obiekty mesh
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            self.report({'ERROR'}, "Brak zaznaczonych obiektów mesh")
            return {'CANCELLED'}
        
        # Pokaż okno dialogowe
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "interval")

    def execute(self, context):
        import bmesh
        import mathutils
        
        # Wyczyść plik debug warstwic
        import os
        debug_file = "/Users/michalmalewczyk/Desktop/warstwice_debug.txt"
        if os.path.exists(debug_file):
            os.remove(debug_file)
        
        debug_contours_log("=== ROZPOCZYNAM GENEROWANIE WARSTWIC ===")

        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        if not selected_meshes:
            debug_contours_log("BŁĄD: Brak zaznaczonych obiektów mesh")
            self.report({'ERROR'}, "Brak zaznaczonych obiektów mesh")
            return {'CANCELLED'}

        debug_contours_log(f"Znaleziono {len(selected_meshes)} zaznaczonych obiektów mesh")
        debug_contours_log(f"Interwał warstwic: {self.interval}")

        contour_count = 0
        
        for target_obj in selected_meshes:
            debug_contours_log(f"Przetwarzam obiekt: {target_obj.name}")
            
            # Usuń istniejące warstwice dla tego obiektu
            self.remove_existing_contours(target_obj)
            
            # Wygeneruj warstwice
            contours = self.generate_contours_for_object(target_obj, self.interval)
            contour_count += len(contours)

        debug_contours_log(f"=== ZAKOŃCZONO: Wygenerowano {contour_count} warstwic dla {len(selected_meshes)} obiektów ===")
        self.report({'INFO'}, f"Wygenerowano {contour_count} warstwic dla {len(selected_meshes)} obiektów")
        return {'FINISHED'}

    def remove_existing_contours(self, parent_obj):
        """Usuwa istniejące obiekty warstwic dla danego obiektu rodzica."""
        children_to_remove = []
        for child in parent_obj.children:
            if child.name.startswith("#Warstwice."):
                children_to_remove.append(child)
        
        for child in children_to_remove:
            bpy.data.objects.remove(child, do_unlink=True)

    def generate_contours_for_object(self, target_obj, interval):
        """Generuje warstwice dla danego obiektu."""
        import bmesh
        import mathutils
        from mathutils import Vector

        # Pobierz dane mesh
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = target_obj.evaluated_get(depsgraph)
        mesh = eval_obj.to_mesh()
        
        if not mesh.vertices:
            debug_contours_log(f"Obiekt {target_obj.name} nie ma vertices")
            return []

        # Znajdź zakres Z w przestrzeni globalnej
        z_coords = [target_obj.matrix_world @ v.co for v in mesh.vertices]
        min_z = min(v.z for v in z_coords)
        max_z = max(v.z for v in z_coords)
        
        debug_contours_log(f"Obiekt {target_obj.name}, zakres Z: {min_z:.3f} do {max_z:.3f}")

        # Oblicz poziomy warstwic - próbkuj co interval od najbliższej wielokrotności interval
        first_level = math.floor(min_z / interval) * interval
        last_level = math.ceil(max_z / interval) * interval
        
        levels = []
        current_level = first_level
        while current_level <= last_level:
            # Dodaj poziom jeśli przecina obiekt (z małym marginesem)
            if min_z - 0.001 <= current_level <= max_z + 0.001:
                levels.append(current_level)
            current_level += interval
        
        debug_contours_log(f"Obliczone poziomy warstwic: {levels}")

        contours = []
        
        for i, level in enumerate(levels):
            debug_contours_log(f"Tworzę warstwicę na poziomie {level:.3f}")
            contour_obj = self.create_contour_at_level(target_obj, mesh, level, i + 1)
            if contour_obj:
                contours.append(contour_obj)
                debug_contours_log(f"Utworzono warstwicę {contour_obj.name}")
            else:
                debug_contours_log(f"Nie udało się utworzyć warstwicy na poziomie {level:.3f}")

        # Zwolnij mesh
        eval_obj.to_mesh_clear()
        
        debug_contours_log(f"Łącznie utworzono {len(contours)} warstwic dla {target_obj.name}")
        return contours

    def create_contour_at_level(self, parent_obj, mesh, z_level, index):
        """Tworzy obiekt warstwicy na danym poziomie Z."""
        import bmesh
        from mathutils import Vector, Matrix

        # Stwórz bmesh z mesh
        bm = bmesh.new()
        bm.from_mesh(mesh)
        
        debug_contours_log(f"Mesh ma {len(bm.verts)} vertices, {len(bm.edges)} edges, {len(bm.faces)} faces")
        
        # Transformuj do przestrzeni globalnej
        bm.transform(parent_obj.matrix_world)

        # Sprawdź czy płaszczyzna przecina mesh
        z_coords = [v.co.z for v in bm.verts]
        min_mesh_z = min(z_coords)
        max_mesh_z = max(z_coords)
        
        debug_contours_log(f"Po transformacji: zakres Z: {min_mesh_z:.3f} do {max_mesh_z:.3f}, poziom cięcia: {z_level:.3f}")
        
        if z_level < min_mesh_z - 0.001 or z_level > max_mesh_z + 0.001:
            debug_contours_log(f"Poziom {z_level:.3f} nie przecina mesh ({min_mesh_z:.3f} - {max_mesh_z:.3f})")
            bm.free()
            return None

        # Nowy zbmesh dla warstwicy
        contour_bm = bmesh.new()
        
        # Przetnij mesh płaszczyzną na poziomie z_level i znajdź przecięcia
        plane_normal = Vector((0, 0, 1))
        tolerance = 0.001
        
        debug_contours_log(f"Szukam przecięć z płaszczyzną Z={z_level:.3f}")
        
        contour_edges_count = 0
        
        # Przejdź przez wszystkie faces i znajdź przecięcia z płaszczyzną
        for face in bm.faces:
            # Znajdź krawędzie face, które przecinają płaszczyznę
            intersections = []
            
            for edge in face.edges:
                v1, v2 = edge.verts
                z1, z2 = v1.co.z, v2.co.z
                
                # Sprawdź czy krawędź przecina płaszczyznę
                if (z1 <= z_level <= z2) or (z2 <= z_level <= z1):
                    if abs(z1 - z2) > tolerance:  # Unikaj dzielenia przez zero
                        # Oblicz punkt przecięcia
                        t = (z_level - z1) / (z2 - z1)
                        intersection_point = v1.co.lerp(v2.co, t)
                        intersections.append(intersection_point)
            
            # Jeśli mamy dokładnie 2 przecięcia, stwórz krawędź warstwicy
            if len(intersections) == 2:
                # Dodaj vertices do contour_bm
                v1 = contour_bm.verts.new(intersections[0])
                v2 = contour_bm.verts.new(intersections[1])
                contour_bm.edges.new([v1, v2])
                contour_edges_count += 1
        
        debug_contours_log(f"Utworzono {contour_edges_count} krawędzi warstwicy")
        
        # Zwolnij oryginalny bmesh
        bm.free()
        
        if contour_edges_count == 0:
            debug_contours_log(f"Brak przecięć na poziomie {z_level:.3f}")
            contour_bm.free()
            return None
        
        # Usuń duplikaty vertices (merge vertices w tej samej lokalizacji)
        bmesh.ops.remove_doubles(contour_bm, verts=contour_bm.verts, dist=0.001)
        
        debug_contours_log(f"Po usunięciu duplikatów: {len(contour_bm.verts)} vertices, {len(contour_bm.edges)} edges")
        
        if not contour_bm.edges:
            debug_contours_log(f"Brak edges po czyszczeniu na poziomie {z_level:.3f}")
            contour_bm.free()
            return None

        # Transformuj warstwice z powrotem do lokalnej przestrzeni obiektu rodzicielskiego
        # Zastosuj odwrotną macierz transformacji
        parent_matrix_inv = parent_obj.matrix_world.inverted()
        contour_bm.transform(parent_matrix_inv)
        
        # Stwórz nowy mesh
        contour_mesh = bpy.data.meshes.new(f"Warstwice_{index:03d}")
        contour_bm.to_mesh(contour_mesh)
        contour_bm.free()

        # Stwórz obiekt
        contour_name = f"#Warstwice.{index:03d}"
        contour_obj = bpy.data.objects.new(contour_name, contour_mesh)
        
        # Dodaj do sceny
        bpy.context.collection.objects.link(contour_obj)
        
        # Ustaw jako dziecko obiektu źródłowego
        contour_obj.parent = parent_obj
        contour_obj.parent_type = 'OBJECT'

        # Ustaw lokację na (0,0,0) - warstwice są już w lokalnej przestrzeni rodzica
        contour_obj.location = (0, 0, 0)
        
        debug_contours_log(f"Utworzono obiekt warstwicy: {contour_name} z {len(contour_mesh.edges)} edges")
        return contour_obj

class MIIXARCH_OT_CreateBuilding(Operator):
    bl_idname = "miixarch.create_building"
    bl_label = "Stwórz budynek"

    def execute(self, context):
        idx = 1
        while f"#Budynek.{idx}" in bpy.data.collections:
            idx += 1
        base_name = f"#Budynek.{idx}"
        context.scene.miixarch_rename_target = base_name
        ensure_building_structure(base_name, context.scene.miixarch_storeys)
        return {'FINISHED'}

class MIIXARCH_OT_CreateArea(Operator):
    bl_idname = "miixarch.create_area"
    bl_label = "Stwórz obszar"

    def execute(self, context):
        idx = 1
        while f"#Obszar.{idx}" in bpy.data.collections:
            idx += 1
        base_name = f"#Obszar.{idx}"
        context.scene.miixarch_area_name = base_name
        ensure_area_structure(base_name)
        return {'FINISHED'}

class MIIXARCH_OT_UpdateBuilding(Operator):
    bl_idname = "miixarch.update_building"
    bl_label = "Zaktualizuj budynek"

    def execute(self, context):
        old = context.scene.miixarch_building_enum
        new = context.scene.miixarch_rename_target.strip()
        if old and new and old != new:
            rename_structure(old, new)
        ensure_building_structure(new or old, context.scene.miixarch_storeys)
        return {'FINISHED'}

class MIIXARCH_OT_UpdateArea(Operator):
    bl_idname = "miixarch.update_area"
    bl_label = "Zaktualizuj obszar"

    def execute(self, context):
        old = context.scene.miixarch_area_enum
        new = context.scene.miixarch_area_name.strip()
        if old and new and old != new:
            rename_structure(old, new)
        ensure_area_structure(new or old)
        return {'FINISHED'}

# Dodaj brakujące panele

class MIIXARCH_PT_ObszaryMainPanel(Panel):
    bl_label = "OBSZARY"
    bl_idname = "MIIXARCH_PT_obszary_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MIIX Architektura"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="OBSZARY", icon="WORLD")
        box.operator("miixarch.create_area")
        box.prop(context.scene, "miixarch_area_enum", text="Obszary")
        if context.scene.miixarch_area_enum:
            box.prop(context.scene, "miixarch_area_name", text="Nazwa obszaru")
            box.operator("miixarch.update_area")
            selected = [obj for obj in context.selected_objects if obj.type == 'MESH']
            if not selected:
                box.label(text="Brak zaznaczonych obiektów.")
            else:
                box.prop(context.scene, "miixarch_object_type", text="Typ obiektu")
                op = box.operator("miixarch.assign_object_type", text="Przypisz")
                op.object_type = context.scene.miixarch_object_type
                box.operator("miixarch.generate_contours", text="Generuj warstwice")
        # Cache DXF statystyki
        cache_box = layout.box()
        cache_box.label(text="Cache DXF", icon='DISK_DRIVE')
        
        # Przycisk statystyk
        row = cache_box.row(align=True)
        row.operator("miixarch.show_dxf_cache_stats", text="Statystyki", icon='INFO')
        row.operator("miixarch.clear_dxf_cache", text="Wyczyść", icon='TRASH')
        
        # Warstwy Text backup
        layers_box = layout.box()
        layers_box.label(text="Backup warstw", icon='TEXT')
        
        row = layers_box.row(align=True)
        row.operator("miixarch.export_layers_to_text", text="Eksportuj", icon='EXPORT')
        row.operator("miixarch.import_layers_from_text", text="Importuj", icon='IMPORT')
        
        layout.separator()
        layout.operator("miix.export_obszar_drawing", icon='EXPORT')

class MIIXARCH_PT_ObszaryLayersPanel(Panel):
    bl_label = "OBSZARY - WARSTWY"
    bl_idname = "MIIXARCH_PT_obszary_layers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MIIX Architektura"
    bl_parent_id = "MIIXARCH_PT_obszary_main"
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        obj = context.active_object
        
        # Sekcja DXF dla zaznaczonego obiektu (na górze)
        if obj and obj.type in ['MESH', 'FONT']:
            box = layout.box()
            box.label(text=f"DXF - {obj.name}", icon='OBJECT_DATA')
            
            # Aktualnie przypisana warstwa
            current_layer = get_object_dxf_layer(obj)
            if current_layer:
                row = box.row()
                row.label(text=f"Obecna warstwa: {current_layer}", icon='LAYER_ACTIVE')
            
            # Wybór warstwy z listy
            row = box.row()
            row.prop(scene, "miixarch_selected_layer", text="Warstwa")
            
            # Ustawienia dla MESH
            if obj.type == 'MESH':
                col = box.column()
                col.label(text="Ustawienia eksportu:")
                
                # Wyświetl obecne ustawienia obiektu (tylko do odczytu)
                current_boundary = get_object_boundary_edges(obj)
                current_internal = get_object_internal_edges(obj)
                current_hatches = get_object_hatches(obj)
                
                info_col = col.column()
                info_col.label(text=f"Krawędzie brzegowe: {'✓' if current_boundary else '✗'}")
                info_col.label(text=f"Krawędzie wewnętrzne: {'✓' if current_internal else '✗'}")
                info_col.label(text=f"Kreskowanie: {'✓' if current_hatches else '✗'}")
                
                col.separator()
                col.label(text="Nowe ustawienia:")
                col.prop(scene, "miixarch_ui_boundary_edges", text="Krawędzie brzegowe")
                col.prop(scene, "miixarch_ui_internal_edges", text="Krawędzie wewnętrzne")
                col.prop(scene, "miixarch_ui_hatches", text="Kreskowanie")
            
            # Przycisk przypisania
            box.operator("miixarch.assign_dxf_settings", icon='CHECKMARK')
            
            layout.separator()
        
        # Przycisk inicjalizacji domyślnych warstw
        if len(scene.miixarch_dxf_layers) == 0:
            layout.operator("miixarch.initialize_default_layers", text="Zainicjuj domyślne warstwy", icon='ADD')
            return
        
        # Przycisk dodawania nowej warstwy i reset
        row = layout.row()
        row.operator("miixarch.add_layer", text="Dodaj warstwę", icon='ADD')
        row.operator("miixarch.initialize_default_layers", text="Reset", icon='FILE_REFRESH')
        
        # Pole wyszukiwania
        row = layout.row()
        row.prop(scene, "miixarch_layer_search", text="", icon='VIEWZOOM')
        
        # Kontrolki rozwijania/zwijania
        row = layout.row(align=True)
        row.operator("miixarch.expand_all_layers", text="Rozwiń wszystkie", icon='TRIA_DOWN')
        row.operator("miixarch.collapse_all_layers", text="Zwiń wszystkie", icon='TRIA_RIGHT')
        
        # Sortowanie alfabetyczne warstw
        sorted_layers = sorted(
            [(i, layer) for i, layer in enumerate(scene.miixarch_dxf_layers)],
            key=lambda x: x[1].name.lower()
        )
        
        # Filtrowanie wg wyszukiwania
        search_filter = scene.miixarch_layer_search.lower()
        if search_filter:
            sorted_layers = [(i, layer) for i, layer in sorted_layers 
                           if search_filter in layer.name.lower()]
        
        # Lista warstw
        box = layout.box()
        
        for original_index, layer in sorted_layers:
            # Nagłówek warstwy z ikoną rozwijania
            row = box.row(align=True)
            
            # Ikona rozwijania/zwijania
            expand_icon = 'TRIA_DOWN' if layer.expanded else 'TRIA_RIGHT'
            row.prop(layer, "expanded", text="", icon=expand_icon, emboss=False)
            
            # Nazwa warstwy
            row.prop(layer, "name", text="")
            
            # Przycisk usuwania
            op = row.operator("miixarch.remove_layer", text="", icon='X')
            op.index = original_index
            
            # Szczegóły warstwy (tylko gdy rozwinięta)
            if layer.expanded:
                # Szczegóły warstwy w kolumnach
                split = box.split(factor=0.5)
                
                # Lewa kolumna - linie
                col_left = split.column()
                col_left.label(text="Linie:")
                col_left.prop(layer, "line_color_type", text="Typ koloru")
                if layer.line_color_type == 'INDEX':
                    col_left.prop(layer, "line_color_index", text="Kolor")
                elif layer.line_color_type == 'RGB':
                    col_left.prop(layer, "line_color_rgb", text="Kolor")
                elif layer.line_color_type == 'PRONEKO':
                    col_left.prop(layer, "line_color_proneko", text="Kolor")
                col_left.prop(layer, "line_weight", text="Grubość")
                col_left.prop(layer, "line_type", text="Typ linii")
                col_left.prop(layer, "line_scale", text="Skala")
                
                # Prawa kolumna - hatche
                col_right = split.column()
                col_right.label(text="Hatche:")
                col_right.prop(layer, "hatch_color_type", text="Typ koloru")
                if layer.hatch_color_type == 'INDEX':
                    col_right.prop(layer, "hatch_color_index", text="Kolor")
                elif layer.hatch_color_type == 'RGB':
                    col_right.prop(layer, "hatch_color_rgb", text="Kolor")
                elif layer.hatch_color_type == 'PRONEKO':
                    col_right.prop(layer, "hatch_color_proneko", text="Kolor")
                col_right.prop(layer, "hatch_weight", text="Grubość")
                col_right.prop(layer, "hatch_pattern", text="Wzór")
                col_right.prop(layer, "hatch_scale", text="Skala")
                col_right.prop(layer, "hatch_rotation", text="Obrót")
            
            # Separator między warstwami
            box.separator()

class MIIXARCH_PT_BudynkiMainPanel(Panel):
    bl_label = "BUDYNKI"
    bl_idname = "MIIXARCH_PT_budynki_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MIIX Architektura"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="BUDYNKI", icon="MOD_BUILD")
        box.operator("miixarch.create_building")
        box.prop(context.scene, "miixarch_building_enum", text="Budynki")
        if context.scene.miixarch_building_enum:
            box.prop(context.scene, "miixarch_rename_target", text="Nazwa budynku")
            box.prop(context.scene, "miixarch_storeys", text="Liczba kondygnacji")
            box.operator("miixarch.update_building")
        box = layout.box()
        box.label(text="OBIEKTY", icon="OBJECT_DATA")
        selected = [obj for obj in context.selected_objects if obj.type in {'MESH', 'CURVE'}]
        if selected:
            box.label(text="Obiekt:")
            for obj in selected:
                box.label(text=obj.name)
            box.separator()
            box.label(text="Rodzaj:")
            box.prop(context.scene, "miixarch_surface_type", text="")
            op = box.operator("miixarch.assign_surface", text="Przypisz")
            op.surface_type = context.scene.miixarch_surface_type
        else:
            box.label(text="Brak zaznaczonych obiektów.")
        # Przycisk eksportu DXF na końcu panelu
        layout.separator()
        layout.operator("miix.update_drawing", icon='FILE_REFRESH')
        layout.operator("miix.export_drawing_layers", icon='EXPORT')

class MIIXARCH_PT_BudynkiLayersPanel(Panel):
    bl_label = "BUDYNKI - WARSTWY"
    bl_idname = "MIIXARCH_PT_budynki_layers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "MIIX Architektura"
    bl_parent_id = "MIIXARCH_PT_budynki_main"
    
    def draw(self, context):
        layout = self.layout
        
# NOTE: Panel DXF Properties przeniesiony do N-panelu OBSZARY - WARSTWY
# Właściwości są teraz przechowywane w Custom Properties

# -----------------------------------------------------------------------------
# Menu dla Link/Transfer Data ------------------------------------------------
# -----------------------------------------------------------------------------

class MIIXARCH_MT_LinkMenu(bpy.types.Menu):
    bl_label = "MIIX"
    bl_idname = "MIIXARCH_MT_link_menu"
    
    def draw(self, context):
        layout = self.layout
        layout.operator("miixarch.copy_dxf_settings", icon='LAYER_ACTIVE')

def draw_miix_link_menu(self, context):
    """Dodaje menu MIIX do Link/Transfer Data"""
    layout = self.layout
    layout.separator()
    layout.menu("MIIXARCH_MT_link_menu", icon='LAYER_ACTIVE')

# Dodaj brakujące handlery

@persistent
def recalculate_area_on_edit(scene):
    obj = bpy.context.active_object
    if obj and obj.type in {'MESH', 'CURVE'} and obj.name.startswith("#Powierzchnia-"):
        # Sprawdź czy to jest typ powierzchni, który ma liczoną powierzchnię
        surface_types_with_area = [
            'netto-uzytkowa',
            'netto-wewnetrzna', 
            'brutto-calkowita',
            'brutto-zabudowy'
        ]
        if any(surface_type in obj.name for surface_type in surface_types_with_area):
            area = calculate_area(obj)
            obj["Powierzchnia"] = area

@persistent
def recalculate_area_object_properties_on_edit(scene):
    """Automatycznie przelicza właściwości obiektów obszarów przy edycji."""
    obj = bpy.context.active_object
    if obj and obj.type == 'MESH':
        obj_name = obj.name
        
        # Obiekty z powierzchnią XY
        if obj_name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy")):
            # Przelicz dla obiektu głównego
            recalculate_area_for_object(obj)
            
            # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
            if obj.data:
                for other_obj in bpy.data.objects:
                    if (other_obj != obj and 
                        other_obj.type == 'MESH' and 
                        other_obj.data == obj.data and
                        other_obj.name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy"))):
                    
                        recalculate_area_for_object(other_obj)
        
        # Obiekty z objętością i głębokością
        elif obj_name.startswith("#Ogród_deszczowy"):
            volume = calculate_volume(obj)
            depth = calculate_depth(obj)
            obj["Objętość"] = round(volume, 4)
            obj["Głębokość"] = round(depth, 2)
            
            # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
            if obj.data:
                for other_obj in bpy.data.objects:
                    if (other_obj != obj and 
                        other_obj.type == 'MESH' and 
                        other_obj.data == obj.data and
                        other_obj.name.startswith("#Ogród_deszczowy")):
                        volume = calculate_volume(other_obj)
                        depth = calculate_depth(other_obj)
                        other_obj["Objętość"] = round(volume, 4)
                        other_obj["Głębokość"] = round(depth, 2)

def recalculate_area_for_object(obj):
    """Pomocnicza funkcja do przeliczania powierzchni dla obiektu."""
    # Użyj nowej funkcji z obsługą OSTAB
    area_data = calculate_area_xy_with_ostab(obj)
    
    # Usuń stare custom properties związane z powierzchnią
    surface_props = ["Powierzchnia", "Powierzchnia w obrębie OSTAB", "Powierzchnia poza OSTAB", "Powierzchnia razem"]
    for prop in surface_props:
        if prop in obj:
            del obj[prop]
    
    # Ustaw nowe custom properties
    for prop_name, value in area_data.items():
        obj[prop_name] = value

# Nowa zmienna globalna do śledzenia trybu edycji
_last_mode = None

@persistent  
def recalculate_on_mode_change(scene):
    """Przelicza powierzchnie gdy użytkownik wychodzi z trybu edycji."""
    global _last_mode
    current_mode = bpy.context.mode
    
    # Sprawdź czy przeszliśmy z trybu edycji do trybu obiektu
    if _last_mode == 'EDIT_MESH' and current_mode == 'OBJECT':
        obj = bpy.context.active_object
        if obj and obj.type == 'MESH':
            obj_name = obj.name
            
            # Obiekty z powierzchnią XY
            if obj_name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy")):
                # Przelicz dla obiektu głównego
                recalculate_area_for_object(obj)
                
                # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
                if obj.data:
                    for other_obj in bpy.data.objects:
                        if (other_obj != obj and 
                            other_obj.type == 'MESH' and 
                            other_obj.data == obj.data and
                            other_obj.name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy"))):
                            recalculate_area_for_object(other_obj)
            
            # Obiekty z objętością i głębokością
            elif obj_name.startswith("#Ogród_deszczowy"):
                volume = calculate_volume(obj)
                depth = calculate_depth(obj)
                obj["Objętość"] = round(volume, 4)
                obj["Głębokość"] = round(depth, 2)
                
                # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
                if obj.data:
                    for other_obj in bpy.data.objects:
                        if (other_obj != obj and 
                            other_obj.type == 'MESH' and 
                            other_obj.data == obj.data and
                            other_obj.name.startswith("#Ogród_deszczowy")):
                            volume = calculate_volume(other_obj)
                            depth = calculate_depth(other_obj)
                            other_obj["Objętość"] = round(volume, 4)
                            other_obj["Głębokość"] = round(depth, 2)
    
    # Aktualizuj ostatni tryb
    _last_mode = current_mode

@persistent
def recalculate_object_type_properties(scene):
    # Przechowuj już przetworzone mesh data, aby uniknąć duplikatów
    processed_mesh_data = set()
    
    for obj in scene.objects:
        if obj.type == 'MESH' and obj.name.startswith("#"):
            # Sprawdź czy mesh data już był przetworzony
            if obj.data in processed_mesh_data:
                continue
                
            if obj.name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy")):
                # Przelicz dla obiektu głównego
                recalculate_area_for_object(obj)
                
                # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
                if obj.data:
                    for other_obj in bpy.data.objects:
                        if (other_obj != obj and 
                            other_obj.type == 'MESH' and 
                            other_obj.data == obj.data and
                            other_obj.name.startswith(("#Teren", "#Deski_tarasowe", "#Kostka_betonowa", "#Kostka_farmerska", "#Opaska_żwirowa", "#Ekokrata", "#Ogród_zimowy"))):
                            recalculate_area_for_object(other_obj)
                
                # Oznacz mesh data jako przetworzony
                processed_mesh_data.add(obj.data)
                
            elif obj.name.startswith("#Ogród_deszczowy"):
                # Oblicz powierzchnię największego face
                largest_face_area = calculate_largest_face_area_xy(obj)
                volume = calculate_volume(obj)
                depth = calculate_depth(obj)
                obj["Powierzchnia"] = round(largest_face_area, 2)
                obj["Objętość"] = round(volume, 4)
                obj["Głębokość"] = round(depth, 2)
                
                # Przelicz także dla wszystkich obiektów, które linkują ten sam mesh data
                if obj.data:
                    for other_obj in bpy.data.objects:
                        if (other_obj != obj and 
                            other_obj.type == 'MESH' and 
                            other_obj.data == obj.data and
                            other_obj.name.startswith("#Ogród_deszczowy")):
                            largest_face_area = calculate_largest_face_area_xy(other_obj)
                            volume = calculate_volume(other_obj)
                            depth = calculate_depth(other_obj)
                            other_obj["Powierzchnia"] = round(largest_face_area, 2)
                            other_obj["Objętość"] = round(volume, 4)
                            other_obj["Głębokość"] = round(depth, 2)
                
                # Oznacz mesh data jako przetworzony
                processed_mesh_data.add(obj.data)

@persistent
def update_rzedna_texts(scene):
    for obj in scene.objects:
        if (obj.type == 'FONT' and 
            obj.name.startswith('#Opis-rzędna-tekst.') and 
            obj.parent and 
            obj.parent.type == 'MESH' and
            obj.parent.name.startswith('#Opis-rzędna.')):
            
            # Użyj relacji rodzic-dziecko zamiast dopasowywania nazw
            parent = obj.parent
            z = parent.matrix_world.translation.z
            z_str = f"{z:.2f}".replace('.', ',')
            if obj.data.body != z_str:
                obj.data.body = z_str

@persistent
def update_poziom_texts(scene):
    """Aktualizuje teksty poziomów i zabezpiecza położenie obiektów Opis-poziom."""
    # Listy obiektów do usunięcia
    objects_to_remove = []
    
    # Najpierw sprawdź obiekty powiązane z vertices
    for obj in scene.objects:
        if (obj.type == 'MESH' and 
            obj.name.startswith('#Opis-poziom.') and
            obj.parent and
            obj.parent_type == 'VERTEX'):
            
            parent_obj = obj.parent
            if not parent_obj or parent_obj.type != 'MESH':
                # Rodzic nie istnieje lub nie jest mesh - oznacz do usunięcia
                objects_to_remove.append(obj)
                continue
            
            # Sprawdź czy vertex z którym jest powiązany nadal istnieje
            try:
                if hasattr(parent_obj, 'data') and hasattr(parent_obj.data, 'vertices'):
                    vertex_indices = obj.parent_vertices
                    if vertex_indices and len(vertex_indices) > 0:
                        vertex_index = vertex_indices[0]
                        
                        # Sprawdź czy vertex index jest prawidłowy
                        if vertex_index >= len(parent_obj.data.vertices):
                            # Vertex nie istnieje - oznacz do usunięcia
                            objects_to_remove.append(obj)
                        # Jeśli vertex istnieje, nie robimy nic z pozycją
                        # Blender sam zarządza pozycją obiektów z vertex parent
                    else:
                        # Brak prawidłowych indices - oznacz do usunięcia
                        objects_to_remove.append(obj)
                else:
                    # Rodzic nie ma vertices - oznacz do usunięcia
                    objects_to_remove.append(obj)
            except (AttributeError, IndexError, TypeError):
                # Błąd dostępu do danych - oznacz do usunięcia
                objects_to_remove.append(obj)
    
    # Następnie aktualizuj teksty poziomów
    for obj in scene.objects:
        if (obj.type == 'FONT' and 
            obj.name.startswith('#Opis-poziom-tekst.') and 
            obj.parent and 
            obj.parent.type == 'MESH' and
            obj.parent.name.startswith('#Opis-poziom.')):
            
            parent = obj.parent
            # Sprawdź czy rodzic jest oznaczony do usunięcia
            if parent in objects_to_remove:
                objects_to_remove.append(obj)
                continue
                
            # Aktualizuj tekst na podstawie pozycji rodzica
            # Dla wszystkich obiektów używaj pozycji obiektu (Blender sam zarządza vertex parent)
            z = parent.matrix_world.translation.z
            
            z_str = f"{z:.2f}".replace('.', ',')
            if obj.data.body != z_str:
                obj.data.body = z_str
    
    # Usuń nieaktualne obiekty
    for obj in objects_to_remove:
        try:
            # Usuń dzieci (tekst) jeśli nie są już na liście
            for child in obj.children:
                if child not in objects_to_remove:
                    bpy.data.objects.remove(child, do_unlink=True)
            
            # Usuń główny obiekt
            bpy.data.objects.remove(obj, do_unlink=True)
        except:
            pass  # Ignoruj błędy usuwania

@persistent
def secure_opis_poziom_positions(scene):
    """Dodatkowe zabezpieczenie pozycji obiektów Opis-poziom - sprawdza czy vertex parent działa poprawnie."""
    try:
        for obj in scene.objects:
            if (obj.type == 'MESH' and 
                obj.name.startswith('#Opis-poziom.') and
                obj.parent and
                obj.parent_type == 'VERTEX'):
                
                parent_obj = obj.parent
                if parent_obj and parent_obj.type == 'MESH':
                    try:
                        vertex_indices = obj.parent_vertices
                        if vertex_indices and len(vertex_indices) > 0:
                            vertex_index = vertex_indices[0]
                            
                            # Sprawdź czy vertex index jest prawidłowy
                            if vertex_index >= len(parent_obj.data.vertices):
                                # Vertex nie istnieje - znajdź najbliższy istniejący vertex
                                if len(parent_obj.data.vertices) > 0:
                                    # Ustaw na ostatni dostępny vertex
                                    new_vertex_index = len(parent_obj.data.vertices) - 1
                                    obj.parent_vertices = [new_vertex_index, new_vertex_index, new_vertex_index]
                                else:
                                    # Brak vertices - przełącz na zwykły parent
                                    obj.parent_type = 'OBJECT'
                                    obj.location = (0, 0, 0)
                            # Jeśli vertex index jest prawidłowy, nie robimy nic
                            # Blender sam zarządza pozycją obiektów z vertex parent
                    except (AttributeError, IndexError, TypeError):
                        # Błąd z vertex parent - przełącz na zwykły parent
                        try:
                            obj.parent_type = 'OBJECT'
                            obj.location = (0, 0, 0)
                        except:
                            pass
    except:
        pass  # Ignoruj wszelkie błędy w handlerze

@persistent
def update_etykieta_rectangles(scene):
    """Aktualizuje rozmiary prostokątów etykiet na podstawie rozmiaru tekstu."""
    try:
        for obj in scene.objects:
            if (obj.type == 'FONT' and 
                obj.name.startswith('#Opis-etykieta-tekst.')):
                
                text_obj = obj
                
                # Znajdź dziecko mesh
                mesh_obj = None
                for child in obj.children:
                    if (child.type == 'MESH' and 
                        child.name.startswith('#Opis-etykieta.')):
                        mesh_obj = child
                        break
                
                if not mesh_obj:
                    continue
                
                obj = mesh_obj  # Dla kompatybilności z resztą kodu
                
                # Pobierz wymiary tekstu w lokalnych współrzędnych
                # Użyj bounding box obiektu Font
                bbox = text_obj.bound_box
                
                # Oblicz rzeczywiste wymiary tekstu
                min_x = min(v[0] for v in bbox)
                max_x = max(v[0] for v in bbox)
                min_y = min(v[1] for v in bbox)
                max_y = max(v[1] for v in bbox)
                
                text_width = max_x - min_x
                text_height = max_y - min_y
                
                # Dodaj margines 0.4 w każdą stronę (0.2 na każdą stronę = 0.4 łącznie)
                rect_width = text_width + 0.4
                rect_height = text_height + 0.4
                
                # Oblicz pozycję prostokąta względem tekstu
                # Tekst ma align LEFT i TOP_BASELINE, więc jego punkt odniesienia to lewy górny róg
                rect_x_offset = -0.2  # Przesunięcie w lewo o 0.2
                rect_y_top = 0.7      # Górne wierzchołki na stałej wartości +0.8
                rect_y_bottom = -text_height + 0.3  # Dolne wierzchołki: -wymiar_font_na_y + 0.4
                
                # Oblicz pozycje wierzchołków prostokąta
                vertices = [
                    (rect_x_offset, rect_y_bottom, 0),  # Lewy dolny
                    (rect_x_offset + rect_width, rect_y_bottom, 0),  # Prawy dolny
                    (rect_x_offset + rect_width, rect_y_top, 0),  # Prawy górny
                    (rect_x_offset, rect_y_top, 0)  # Lewy górny
                ]
                
                # Aktualizuj tylko pierwsze 4 wierzchołki (prostokąt), pozostaw dodatkowe nietknięte
                mesh = obj.data
                
                # Sprawdź czy mamy co najmniej 4 wierzchołki
                if len(mesh.vertices) >= 4:
                    # Porównaj pierwsze 4 wierzchołki z nowymi pozycjami
                    needs_update = False
                    for i in range(4):
                        curr = mesh.vertices[i].co
                        new = vertices[i]
                        if abs(curr[0] - new[0]) > 0.001 or abs(curr[1] - new[1]) > 0.001:
                            needs_update = True
                            break
                    
                    if needs_update:
                        # Aktualizuj tylko pozycje pierwszych 4 wierzchołków
                        for i in range(4):
                            mesh.vertices[i].co = vertices[i]
                        mesh.update()
                elif len(mesh.vertices) == 0:
                    # Jeśli mesh jest pusty, utwórz podstawowy prostokąt
                    faces = [(0, 1, 2, 3)]
                    mesh.from_pydata(vertices, [], faces)
                    mesh.update()
    except:
        pass  # Ignoruj błędy w handlerze

@persistent
def update_ogrod_deszczowy_properties(scene):
    """Aktualizuje custom property 'Powierzchnia' dla obiektów #Ogród_deszczowy."""
    try:
        for obj in scene.objects:
            if (obj.type == 'MESH' and 
                obj.name.startswith('#Ogród_deszczowy.') and
                len(obj.name.split('.')) == 2):  # Format #Ogród_deszczowy.XXX
                
                # Oblicz powierzchnię największego face
                largest_face_area = calculate_largest_face_area_xy(obj)
                
                # Ustaw custom property
                obj["Powierzchnia"] = largest_face_area
                
                # Upewnij się, że custom property "Głębokość" istnieje
                if "Głębokość" not in obj:
                    obj["Głębokość"] = 0.0
    except:
        pass  # Ignoruj błędy w handlerze

@persistent
def auto_create_etykieta_mesh_objects(scene):
    """Automatycznie tworzy obiekty Mesh dla obiektów Opis-etykieta-tekst, które ich nie mają."""
    try:
        for obj in scene.objects:
            if (obj.type == 'FONT' and 
                obj.name.startswith('#Opis-etykieta-tekst.') and
                len(obj.name.split('.')) == 2):  # Sprawdź że ma format #Opis-etykieta-tekst.XXX
                
                # Wyciagnij numer z nazwy obiektu
                try:
                    suffix = obj.name.split('.')[-1]
                    expected_mesh_name = f"#Opis-etykieta.{suffix}"
                    
                    # Sprawdź czy obiekt ma dziecko mesh
                    has_mesh_child = any(child.type == 'MESH' and 
                                       child.name.startswith("#Opis-etykieta.") 
                                       for child in obj.children)
                    
                    if not has_mesh_child:
                        # Utwórz obiekt Mesh używając podobnej logiki jak w operatorze
                        create_etykieta_mesh_object_standalone(obj, expected_mesh_name, bpy.context)
                except (ValueError, IndexError):
                    # Ignoruj obiekty z nieprawidłową nazwą
                    pass
    except:
        pass  # Ignoruj błędy w handlerze

def create_etykieta_mesh_object_standalone(text_obj, mesh_name, context):
    """Tworzy obiekt Mesh dla obiektu Opis-etykieta-tekst - wersja standalone."""
    try:
        # Utwórz mesh data dla prostokąta
        mesh_data = bpy.data.meshes.new(mesh_name)
        
        # Początkowe wymiary prostokąta (będą aktualizowane przez handler)
        # Górne wierzchołki na +0.8, dolne dostosowane do wysokości tekstu
        vertices = [
            (-0.2, -0.8, 0),  # Lewy dolny (tymczasowo, handler zaktualizuje)
            (0.2, -0.8, 0),   # Prawy dolny (tymczasowo, handler zaktualizuje)
            (0.2, 0.8, 0),    # Prawy górny (stała wartość +0.8)
            (-0.2, 0.8, 0)    # Lewy górny (stała wartość +0.8)
        ]
        faces = [(0, 1, 2, 3)]
        
        mesh_data.from_pydata(vertices, [], faces)
        mesh_data.update()
        
        # Utwórz obiekt Mesh (dziecko)
        mesh_obj = bpy.data.objects.new(mesh_name, mesh_data)
        mesh_obj.location = (0, 0, 0)  # Lokalne współrzędne 0,0,0
        mesh_obj.parent = text_obj
        
        # Dodaj do tej samej kolekcji co rodzic
        for collection in text_obj.users_collection:
            collection.objects.link(mesh_obj)
            break
        else:
            # Fallback - dodaj do aktywnej kolekcji
            context.collection.objects.link(mesh_obj)
            
    except Exception as e:
        # W przypadku błędu, nie rób nic
        pass

@persistent
def auto_create_ogrod_deszczowy_labels(scene):
    """Automatycznie tworzy etykiety dla obiektów #Ogród_deszczowy i migruje istniejące do właściwych kolekcji."""
    try:
        for obj in scene.objects:
            if (obj.type == 'MESH' and 
                obj.name.startswith('#Ogród_deszczowy.') and
                len(obj.name.split('.')) == 2):  # Format #Ogród_deszczowy.XXX
                
                # Sprawdź czy ogród deszczowy ma już dziecko-etykietę (jakiekolwiek dziecko typu FONT)
                existing_label = None
                for child in obj.children:
                    if child.type == 'FONT' and child.name.startswith('#Opis-etykieta-tekst'):
                        existing_label = child
                        break
                
                if existing_label:
                    # Etykieta istnieje - sprawdź czy jest w właściwej kolekcji
                    # Znajdź właściwą kolekcję #Obszar.X-Opis-Deszcz
                    target_collection = None
                    for collection in obj.users_collection:
                        if collection.name.startswith('#Obszar.'):
                            try:
                                obszar_parts = collection.name.split('.')
                                if len(obszar_parts) >= 2:
                                    obszar_number = obszar_parts[1]
                                    target_collection_name = f"#Obszar.{obszar_number}-Opis-Deszcz"
                                    
                                    if target_collection_name in bpy.data.collections:
                                        target_collection = bpy.data.collections[target_collection_name]
                                    break
                            except (ValueError, IndexError):
                                continue
                    
                    # Sprawdź czy etykieta jest w właściwej kolekcji
                    if target_collection and existing_label not in target_collection.objects:
                        # Usuń z wszystkich kolekcji
                        for coll in existing_label.users_collection:
                            coll.objects.unlink(existing_label)
                        # Dodaj do właściwej kolekcji
                        target_collection.objects.link(existing_label)
                        
                        # Sprawdź też mesh prostokąt (dziecko etykiety)
                        for mesh_child in existing_label.children:
                            if (mesh_child.type == 'MESH' and 
                                mesh_child.name.startswith("#Opis-etykieta")):
                                if mesh_child not in target_collection.objects:
                                    # Usuń z wszystkich kolekcji
                                    for coll in mesh_child.users_collection:
                                        coll.objects.unlink(mesh_child)
                                    # Dodaj do właściwej kolekcji
                                    target_collection.objects.link(mesh_child)
                else:
                    # Etykieta nie istnieje - utwórz nową ze standardową nazwą
                    label_name = "#Opis-etykieta-tekst"  # Blender automatycznie doda .001, .002 itd.
                    create_ogrod_deszczowy_label_standalone(obj, label_name, bpy.context)
    except:
        pass  # Ignoruj błędy w handlerze

def create_ogrod_deszczowy_label_standalone(ogrod_obj, label_name, context):
    """Tworzy etykietę dla obiektu #Ogród_deszczowy - wersja standalone."""
    try:
        # Wyciągnij numer z nazwy obiektu
        suffix = ogrod_obj.name.split('.')[-1]
        
        # Pobierz wartości z custom properties
        powierzchnia = ogrod_obj.get("Powierzchnia", 0.0)
        glebokosc = ogrod_obj.get("Głębokość", 0.0)
        objetosc = powierzchnia * glebokosc  # Oblicz objętość
        
        # Stwórz tekst etykiety
        powierzchnia_str = f"{powierzchnia:.2f}".replace('.', ',')
        glebokosc_str = f"{glebokosc:.2f}".replace('.', ',')
        objetosc_str = f"{objetosc:.2f}".replace('.', ',')
        
        label_text = f"""Ogród deszczowy nr {suffix}
Powierzchnia - {powierzchnia_str} m²
Głębokość - {glebokosc_str} m
Objętość - {objetosc_str} m³"""
        
        # Utwórz obiekt Font (etykieta)
        curve_data = bpy.data.curves.new(name=label_name, type='FONT')
        curve_data.body = label_text
        curve_data.size = 0.175953 * 5  # Taki sam rozmiar jak inne etykiety
        curve_data.use_fast_edit = True
        curve_data.align_x = 'LEFT'
        curve_data.align_y = 'TOP_BASELINE'
        
        # Ustaw font jeśli dostępny
        try:
            if "Montserrat Thin" in bpy.data.fonts:
                curve_data.font = bpy.data.fonts["Montserrat Thin"]
            elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                for font in bpy.data.fonts:
                    if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                        curve_data.font = font
                        break
        except:
            pass  # Użyj domyślnego fontu
        
        # Utwórz obiekt Font
        text_obj = bpy.data.objects.new(label_name, curve_data)
        text_obj.location = (0, 0, 0)  # Lokalne współrzędne 0,0,0
        text_obj.parent = ogrod_obj
        
        # Znajdź właściwą kolekcję #Obszar.X-Opis-Deszcz
        target_collection = None
        
        # Znajdź kolekcję obszaru, w której znajduje się ogród deszczowy
        for collection in ogrod_obj.users_collection:
            if collection.name.startswith('#Obszar.'):
                # Wyciągnij numer obszaru
                try:
                    obszar_parts = collection.name.split('.')
                    if len(obszar_parts) >= 2:
                        obszar_number = obszar_parts[1]
                        # Szukaj kolekcji #Obszar.X-Opis-Deszcz
                        target_collection_name = f"#Obszar.{obszar_number}-Opis-Deszcz"
                        
                        # Sprawdź czy kolekcja już istnieje
                        if target_collection_name in bpy.data.collections:
                            target_collection = bpy.data.collections[target_collection_name]
                        break
                except (ValueError, IndexError):
                    continue
        
        # Dodaj etykietę do właściwej kolekcji
        if target_collection:
            target_collection.objects.link(text_obj)
        else:
            # Fallback - dodaj do tej samej kolekcji co rodzic
            for collection in ogrod_obj.users_collection:
                collection.objects.link(text_obj)
                break
            else:
                # Ostateczny fallback - dodaj do aktywnej kolekcji
                context.collection.objects.link(text_obj)
        
        # Utwórz odpowiadający mesh prostokąt używając istniejącej funkcji
        mesh_name = "#Opis-etykieta"  # Blender automatycznie doda .001, .002 itd.
        create_etykieta_mesh_object_standalone(text_obj, mesh_name, context)
            
    except Exception as e:
        # W przypadku błędu, nie rób nic
        pass

@persistent
def update_ogrod_deszczowy_labels(scene):
    """Aktualizuje tekst etykiet dla obiektów #Ogród_deszczowy na podstawie custom properties."""
    try:
        for obj in scene.objects:
            if (obj.type == 'FONT' and 
                obj.name.startswith('#Opis-etykieta-tekst') and
                obj.parent and
                obj.parent.type == 'MESH' and
                obj.parent.name.startswith('#Ogród_deszczowy.')):
                
                parent = obj.parent
                
                # Wyciągnij numer z nazwy rodzica
                try:
                    suffix = parent.name.split('.')[-1]
                    
                    # Pobierz wartości z custom properties rodzica
                    powierzchnia = parent.get("Powierzchnia", 0.0)
                    glebokosc = parent.get("Głębokość", 0.0)
                    objetosc = powierzchnia * glebokosc  # Oblicz objętość
                    
                    # Stwórz tekst etykiety
                    powierzchnia_str = f"{powierzchnia:.2f}".replace('.', ',')
                    glebokosc_str = f"{glebokosc:.2f}".replace('.', ',')
                    objetosc_str = f"{objetosc:.2f}".replace('.', ',')
                    
                    new_text = f"""Ogród deszczowy nr {suffix}
Powierzchnia - {powierzchnia_str} m²
Głębokość - {glebokosc_str} m
Objętość - {objetosc_str} m³"""
                    
                    # Aktualizuj tekst jeśli się zmienił
                    if obj.data.body != new_text:
                        obj.data.body = new_text
                        
                except (ValueError, IndexError):
                    # Ignoruj obiekty z nieprawidłową nazwą
                    pass
    except:
        pass  # Ignoruj błędy w handlerze

@persistent
def update_spadek_texts(scene):
    import mathutils
    for obj in scene.objects:
        if (obj.type == 'FONT' and 
            obj.name.startswith('#Opis-spadek-tekst.') and 
            obj.parent and 
            obj.parent.type == 'MESH' and
            obj.parent.name.startswith('#Opis-spadek.')):
            
            # Użyj relacji rodzic-dziecko zamiast dopasowywania nazw
            parent = obj.parent
            rot_y = parent.rotation_euler.y
            
            # Automatyczna korekta obrotu - utrzymuj w przedziale -90° do 90°
            rot_y_degrees = math.degrees(rot_y)
            
            # Normalizuj do przedziału -180° do 180°
            while rot_y_degrees > 180:
                rot_y_degrees -= 360
            while rot_y_degrees < -180:
                rot_y_degrees += 360
            
            # Sprawdź czy potrzebna korekta do przedziału -90° do 90°
            corrected = False
            if rot_y_degrees > 90:
                rot_y_degrees -= 180
                corrected = True
            elif rot_y_degrees < -90:
                rot_y_degrees += 180
                corrected = True
            
            # Zastosuj korekcję jeśli była potrzebna
            if corrected:
                corrected_rot_y = math.radians(rot_y_degrees)
                parent.rotation_euler.y = corrected_rot_y
                rot_y = corrected_rot_y
            
            slope = 100 * math.tan(rot_y)
            
            # ZAWSZE ustaw skalę mesh rodzica na osi X zgodnie z obrotem na osi Y
            # Wartość bezwzględna skali X powinna być taka sama jak skala Y
            if rot_y >= 0:
                # Obrót dodatni -> skala mesh = +|scale.y|
                parent.scale.x = abs(parent.scale.y)
            else:
                # Obrót ujemny -> skala mesh = -|scale.y|
                parent.scale.x = -abs(parent.scale.y)
            
            # Ustaw skalę X obiektu Font z tą samą wartością bezwzględną co skala Y, ale z odpowiednim znakiem
            if rot_y >= 0:
                # Obrót dodatni -> skala X = +|scale.y|
                target_scale_x = abs(obj.scale.y)
            else:
                # Obrót ujemny -> skala X = -|scale.y|
                target_scale_x = -abs(obj.scale.y)
            
            if obj.scale.x != target_scale_x:
                obj.scale.x = target_scale_x
            
            # Używaj zawsze wartości bezwzględnej spadku do wyświetlania
            slope = abs(slope)
            slope_str = f"{slope:.2f}".replace('.', ',') + '%'
            if obj.data.body != slope_str:
                obj.data.body = slope_str

@persistent
def auto_create_opis_spadek_text_objects(scene):
    """Automatycznie tworzy obiekty Font dla obiektów Opis-spadek, które ich nie mają."""
    for obj in scene.objects:
        if (obj.type == 'MESH' and 
            obj.name.startswith('#Opis-spadek.') and
            len(obj.name.split('.')) == 2):  # Sprawdź że ma format #Opis-spadek.XXX
            
            # Wyciągnij numer z nazwy obiektu
            try:
                suffix = obj.name.split('.')[-1]
                expected_text_name = f"#Opis-spadek-tekst.{suffix}"
                
                # Sprawdź czy obiekt Font już istnieje
                text_obj = scene.objects.get(expected_text_name)
                if not text_obj:
                    # Sprawdź czy obiekt ma dziecko typu Font (może mieć inną nazwę)
                    has_font_child = any(child.type == 'FONT' and 
                                       child.name.startswith("#Opis-spadek-tekst.") 
                                       for child in obj.children)
                    
                    if not has_font_child:
                        # Utwórz obiekt Font używając istniejącej funkcji
                        create_spadek_text_object_standalone(obj, expected_text_name, bpy.context)
            except (ValueError, IndexError):
                # Ignoruj obiekty z nieprawidłową nazwą
                pass

def create_spadek_text_object_standalone(spadek_obj, text_name, context):
    """Tworzy obiekt Font dla obiektu spadek - wersja standalone."""
    # Domyślny tekst spadku (może być aktualizowany później)
    default_text = "0,0%"
    
    # Utwórz curve data
    curve_data = bpy.data.curves.new(name=text_name, type='FONT')
    curve_data.body = default_text
    curve_data.size = 0.175953 * 5  # 5 razy większy niż surface font
    curve_data.use_fast_edit = True
    curve_data.align_x = 'CENTER'  # Wyśrodkowanie poziome
    
    # Ustaw font jeśli dostępny (taki sam jak w Opis-poziom)
    try:
        if "Montserrat Thin" in bpy.data.fonts:
            curve_data.font = bpy.data.fonts["Montserrat Thin"]
        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
            for font in bpy.data.fonts:
                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                    curve_data.font = font
                    break
    except:
        pass  # Użyj domyślnego fontu
    
    # Utwórz obiekt
    text_obj = bpy.data.objects.new(text_name, curve_data)
    
    # Dodaj do tej samej kolekcji co rodzic
    for collection in spadek_obj.users_collection:
        collection.objects.link(text_obj)
        break  # Dodaj tylko do pierwszej znalezionej kolekcji
    
    # Ustaw jako dziecko
    text_obj.parent = spadek_obj
    text_obj.parent_type = 'OBJECT'
    
    # Ustaw pozycję względem rodzica (0,20,0 → 0,0.20,0)
    text_obj.location = (0, 0.20, 0)
    
    return text_obj

@persistent
def update_surface_text_objects(scene):
    """Aktualizuje obiekty Font dla powierzchni netto użytkowych na podstawie ich rodzica."""
    # Najpierw stwórz teksty dla obiektów mesh, które ich nie mają
    for obj in scene.objects:
        if obj.type == 'MESH' and is_surface_netto_uzytkowa(obj.name):
            # Sprawdź czy ma dziecko typu tekst
            has_text_child = any(child.type == 'FONT' and child.name.startswith("#Powierzchnia-netto-uzytkowa-text.") 
                               for child in obj.children)
            if not has_text_child:
                create_surface_text_object(obj)
    
    # Następnie aktualizuj wszystkie istniejące obiekty tekstu na podstawie ich rodzica
    for text_obj in scene.objects:
        if (text_obj.type == 'FONT' and 
            text_obj.name.startswith("#Powierzchnia-netto-uzytkowa-text.") and 
            text_obj.parent):
            
            parent_obj = text_obj.parent
            if (parent_obj.type == 'MESH' and 
                is_surface_netto_uzytkowa(parent_obj.name)):
                
                # Pobierz powierzchnię od rodzica
                area_value = parent_obj.get("Powierzchnia", 0.0)
                formatted_area = f"{area_value:.2f}".replace('.', ',') + " m²"
                
                # Aktualizuj tekst
                if text_obj.data and hasattr(text_obj.data, 'body'):
                    if text_obj.data.body != formatted_area:
                        text_obj.data.body = formatted_area
                
                # Synchronizuj skalę z obiektem rodzica
                text_obj.scale = parent_obj.scale.copy()
                # Synchronizuj obrót z obiektem rodzica (ze znakiem przeciwnym)
                text_obj.rotation_euler = (-parent_obj.rotation_euler.x, -parent_obj.rotation_euler.y, -parent_obj.rotation_euler.z)

@persistent
def update_lokal_summary_text_objects(scene):
    """Tworzy i aktualizuje obiekty Font z sumą powierzchni dla kolekcji lokali."""
    import re
    
    for collection in bpy.data.collections:
        # Sprawdź czy to kolekcja lokalu
        match = re.match(r'#Budynek\.([A-Z])_Lokal\.(\d+)', collection.name)
        if not match:
                continue
            
        building_letter = match.group(1)
        lokal_number = match.group(2)
        text_name = collection.name
        text_obj = scene.objects.get(text_name)
        
        # Znajdź wszystkie obiekty powierzchni w kolekcji i zsumuj powierzchnie
        total_area = 0.0
        surface_objects = []
        
        def collect_from_collection(coll):
            nonlocal total_area
            for obj in coll.objects:
                if obj.type == 'MESH' and is_surface_netto_uzytkowa(obj.name):
                    area_value = obj.get("Powierzchnia", 0.0)
                    total_area += area_value
                    surface_objects.append(obj)
            
            # Rekurencyjnie sprawdź podkolekcje
            for child_coll in coll.children:
                collect_from_collection(child_coll)
        
        collect_from_collection(collection)
        
        if not surface_objects:
            # Jeśli nie ma obiektów powierzchni, usuń obiekt tekstu jeśli istnieje
            if text_obj and collection in text_obj.users_collection:
                collection.objects.unlink(text_obj)
                if not text_obj.users_collection:
                    bpy.data.objects.remove(text_obj, do_unlink=True)
                continue
        
        # Sformatuj nowy tekst
        formatted_area = f"{total_area:.2f}".replace('.', ',') + " m²"
        display_text = f"Lokal {lokal_number} {formatted_area}"
        
        if not text_obj:
            # Utwórz nowy obiekt tekstu
            create_lokal_summary_text_object(collection)
        else:
            # Aktualizuj istniejący obiekt - tylko tekst
            if text_obj.data and hasattr(text_obj.data, 'body'):
                if text_obj.data.body != display_text:
                    text_obj.data.body = display_text
            
            # Zsynchronizuj skalę i obrót z pierwszym obiektem powierzchni – identycznie jak w update_surface_text_objects
            if surface_objects:
                parent_obj = surface_objects[0]
                # Synchronizuj skalę z obiektem rodzica
                text_obj.scale = parent_obj.scale.copy()
                # Synchronizuj obrót z obiektem rodzica (ze znakiem przeciwnym)
                text_obj.rotation_euler = (-parent_obj.rotation_euler.x, -parent_obj.rotation_euler.y, -parent_obj.rotation_euler.z)

def is_surface_netto_uzytkowa(obj_name):
    """Sprawdza czy nazwa obiektu to powierzchnia netto użytkowa (z lub bez sufiksu)"""
    return (obj_name == "#Powierzchnia-netto-uzytkowa" or 
            obj_name.startswith("#Powierzchnia-netto-uzytkowa."))

def get_surface_suffix(obj_name):
    """Zwraca sufiks dla obiektu powierzchni (lub '001' dla obiektów bez sufiksu)"""
    if obj_name == "#Powierzchnia-netto-uzytkowa":
        return "001"  # Domyślny sufiks dla obiektu bez numeru
    elif obj_name.startswith("#Powierzchnia-netto-uzytkowa."):
        return obj_name.split(".")[-1]
    return None

def create_surface_text_object(surface_obj):
    """Tworzy obiekt Font jako dziecko dla obiektu powierzchni."""
    if not surface_obj or not is_surface_netto_uzytkowa(surface_obj.name):
        return None
    
    # Wyciągnij numer z nazwy rodzica używając pomocniczej funkcji
    suffix = get_surface_suffix(surface_obj.name)
    if not suffix:
        return None
        
    text_name = f"#Powierzchnia-netto-uzytkowa-text.{suffix}"
    
    # Pobierz wartość powierzchni i sformatuj
    area_value = surface_obj.get("Powierzchnia", 0.0)
    formatted_area = f"{area_value:.2f}".replace('.', ',') + " m²"
    
    # Sprawdź czy obiekt już istnieje
    if text_name in bpy.data.objects:
        existing_obj = bpy.data.objects[text_name]
        
        # Zaktualizuj właściwości istniejącego obiektu
        if existing_obj.data:
            # Sprawdź i zaktualizuj size
            target_size = 0.175953
            if abs(existing_obj.data.size - target_size) > 0.001:
                existing_obj.data.size = target_size
            
            # Sprawdź i zaktualizuj use_fast_edit
            if not existing_obj.data.use_fast_edit:
                existing_obj.data.use_fast_edit = True
            
            # Sprawdź i zaktualizuj font jeśli dostępny
            try:
                if "Montserrat Thin" in bpy.data.fonts:
                    if existing_obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                        existing_obj.data.font = bpy.data.fonts["Montserrat Thin"]
                elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                    for font in bpy.data.fonts:
                        if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                            if existing_obj.data.font != font:
                                existing_obj.data.font = font
                            break
            except:
                pass
        
        return existing_obj
    
    # Utwórz curve data
    curve_data = bpy.data.curves.new(name=text_name, type='FONT')
    curve_data.body = formatted_area
    curve_data.size = 0.175953
    curve_data.use_fast_edit = True
    
    # Ustaw font jeśli dostępny
    try:
        if "Montserrat Thin" in bpy.data.fonts:
            curve_data.font = bpy.data.fonts["Montserrat Thin"]
        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
            for font in bpy.data.fonts:
                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                    curve_data.font = font
                    break
    except:
        pass  # Użyj domyślnego fontu
    
    # Utwórz obiekt
    text_obj = bpy.data.objects.new(text_name, curve_data)
    
    # Dodaj do tej samej kolekcji co rodzic
    for coll in surface_obj.users_collection:
        coll.objects.link(text_obj)
        break
    
    # Ustaw jako dziecko
    text_obj.parent = surface_obj
    text_obj.parent_type = 'OBJECT'
    
    # Umieść w środku bounding box rodzica
    bbox_center = sum((Vector(corner) for corner in surface_obj.bound_box), Vector()) / 8
    text_obj.location = bbox_center
    text_obj.rotation_euler = (-surface_obj.rotation_euler.x, -surface_obj.rotation_euler.y, -surface_obj.rotation_euler.z)
    text_obj.scale = surface_obj.scale.copy()
    
    return text_obj

def create_lokal_summary_text_object(collection):
    """Tworzy obiekt Font z sumą powierzchni dla kolekcji lokalu."""
    import re
    
    # Sprawdź czy to kolekcja lokalu
    match = re.match(r'#Budynek\.([A-Z])_Lokal\.(\d+)', collection.name)
    if not match:
        return None
    
    building_letter = match.group(1)
    lokal_number = match.group(2)
    text_name = collection.name
    
    # Sprawdź czy obiekt już istnieje
    if text_name in bpy.data.objects:
        existing_obj = bpy.data.objects[text_name]
        # Sprawdź czy jest w tej kolekcji
        if collection in existing_obj.users_collection:
            # Zaktualizuj właściwości istniejącego obiektu
            if existing_obj.data:
                # Sprawdź i zaktualizuj size
                target_size = 0.219941
                if abs(existing_obj.data.size - target_size) > 0.001:
                    existing_obj.data.size = target_size
                    font_updated_count += 1
                
                # Sprawdź i zaktualizuj use_fast_edit
                if not existing_obj.data.use_fast_edit:
                    existing_obj.data.use_fast_edit = True
                
                # Sprawdź i zaktualizuj font jeśli dostępny
                try:
                    if "Montserrat Thin" in bpy.data.fonts:
                        if existing_obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                            existing_obj.data.font = bpy.data.fonts["Montserrat Thin"]
                    elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                        for font in bpy.data.fonts:
                            if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                                if existing_obj.data.font != font:
                                    existing_obj.data.font = font
                                break
                except:
                    pass
            return existing_obj
    
    # Znajdź wszystkie obiekty powierzchni w kolekcji i zsumuj powierzchnie
    total_area = 0.0
    surface_objects = []
    
    def collect_from_collection(coll):
        nonlocal total_area
        for obj in coll.objects:
            if obj.type == 'MESH' and is_surface_netto_uzytkowa(obj.name):
                area_value = obj.get("Powierzchnia", 0.0)
                total_area += area_value
                surface_objects.append(obj)
        
        # Rekurencyjnie sprawdź podkolekcje
        for child_coll in coll.children:
            collect_from_collection(child_coll)
    
    collect_from_collection(collection)
    
    if not surface_objects:
        return None
    
    # Oblicz bounding box wszystkich obiektów powierzchni
    min_coords = [float('inf')] * 3
    max_coords = [float('-inf')] * 3
    
    for obj in surface_objects:
        for corner in obj.bound_box:
            world_corner = obj.matrix_world @ Vector(corner)
            for i in range(3):
                min_coords[i] = min(min_coords[i], world_corner[i])
                max_coords[i] = max(max_coords[i], world_corner[i])
    
    bbox_center = Vector([(min_coords[i] + max_coords[i]) / 2 for i in range(3)])
    
    # Sformatuj tekst
    formatted_area = f"{total_area:.2f}".replace('.', ',') + " m²"
    display_text = f"Lokal {lokal_number} {formatted_area}"
    
    # Utwórz curve data
    curve_data = bpy.data.curves.new(name=text_name, type='FONT')
    curve_data.body = display_text
    curve_data.size = 0.219941
    curve_data.use_fast_edit = True
    
    # Ustaw font jeśli dostępny
    try:
        if "Montserrat Thin" in bpy.data.fonts:
            curve_data.font = bpy.data.fonts["Montserrat Thin"]
        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
            for font in bpy.data.fonts:
                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                    curve_data.font = font
                    break
    except:
        pass  # Użyj domyślnego fontu
    
    # Utwórz obiekt
    text_obj = bpy.data.objects.new(text_name, curve_data)
    
    # Dodaj do kolekcji lokalu
    collection.objects.link(text_obj)
    
    # Ustaw rodzica – pierwszy napotkany obiekt powierzchni (jeśli istnieje)
    if surface_objects:
        parent_obj = surface_objects[0]
        text_obj.parent = parent_obj
        text_obj.parent_type = 'OBJECT'

    # Umieść w środku bounding box wszystkich powierzchni (pozycja w układzie świata)
    text_obj.location = bbox_center

    # Ustaw rotację i skalę tak, aby odpowiadały wartościom rodzica (jeśli jest ustawiony)
    if surface_objects:
        text_obj.rotation_euler = (-parent_obj.rotation_euler.x,
                                   -parent_obj.rotation_euler.y,
                                   -parent_obj.rotation_euler.z)
        text_obj.scale = parent_obj.scale.copy()
    else:
        text_obj.rotation_euler = (0, 0, 0)
        text_obj.scale = (1, 1, 1)

    return text_obj

class MIIX_OT_update_drawing(bpy.types.Operator):
    bl_idname = "miix.update_drawing"
    bl_label = "Aktualizuj rysunek"
    bl_description = "Generuje geometrię przekroju, widoku i warstwy 'nad' dla aktywnej kamery"

    def execute(self, context):
        import time
        start_time = time.time()
        
        # Sprawdź płaszczyznę cięcia
        plane = get_cutting_plane(context)
        if plane is None:
            self.report({'ERROR'}, "Brak aktywnej kamery")
            return {'CANCELLED'}
        
        cam, origin, normal = plane
        
        # Inicjalizuj logowanie
        directory = os.path.dirname(bpy.path.abspath(context.scene.render.filepath)) or bpy.path.abspath('//') or os.getcwd()
        log_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        global _log_file
        # _log_file = os.path.join(directory, f"update_{cam.name}_{log_time}.txt")  # Logowanie dezaktywowane
        
        
        # Znajdź lub utwórz kolekcję o nazwie kamery
        camera_coll_name = cam.name
        camera_coll = bpy.data.collections.get(camera_coll_name)
        
        # Sprawdź czy kamera jest w jakiejś kolekcji
        parent_coll = None
        for coll in bpy.data.collections:
            if cam.name in coll.objects:
                parent_coll = coll
                break
        
        # Jeśli kolekcja nie istnieje, utwórz ją
        if not camera_coll:
            camera_coll = bpy.data.collections.new(camera_coll_name)
            if parent_coll:
                # Dodaj jako podkolekcję
                parent_coll.children.link(camera_coll)
            else:
                # Dodaj do sceny
                context.scene.collection.children.link(camera_coll)
        else:
            # Kolekcja istnieje - wyczyść jej zawartość
            for obj in list(camera_coll.objects):
                bpy.data.objects.remove(obj, do_unlink=True)
        
        # Zbierz widoczne obiekty MESH (wykluczając #Meble, #Oś i #Przekrój)
        visible = [o for o in context.scene.objects 
                  if o.type == 'MESH' and o.visible_get() and not o.name.startswith('#Meble') 
                  and not ('#Oś' in o.name or '#Os' in o.name) 
                  and not ('#Przekrój' in o.name or '#Przekroj' in o.name)]
        

        
        if not visible:
            self.report({'WARNING'}, "Brak widocznych obiektów mesh do przetworzenia")
            return {'CANCELLED'}
        
        
        total_objects = len(visible)
        successful_objects = 0
        section_objects = 0
        depth_objects = 0
        
        # Cache parametrów kamery
        cam_clip_start = cam.data.clip_start
        cam_clip_end = cam.data.clip_end
        
        # Reset statystyk cache na początku
        CACHE_STATS["section_objects"].clear()
        
        # Przetwarzaj obiekty MESH
        for i, obj in enumerate(visible):
            # Sprawdź timeout co 50 obiektów
            if i % 50 == 0 and time.time() - start_time > 300:  # 5 minut
                self.report({'ERROR'}, f"Timeout po 5 minutach. Przetworzono {successful_objects}/{total_objects} obiektów.")
                break
            
            try:
                # Standardowe przetwarzanie dla zwykłych obiektów
                # 1. Próbuj section_mesh z cache
                section_result = section_mesh(obj, origin, normal, camera_coll)
                if section_result:
                    section_objects += 1
                
                # 2. depth_mesh tylko jeśli NIE ma przekroju (automatyczne wykluczanie)
                widok_result = depth_mesh(obj, cam, origin, normal, camera_coll, context, cam_clip_start, cam_clip_end, "_widok")
                if widok_result:
                    depth_objects += 1
                    
                nad_result = depth_mesh(obj, cam, origin, normal, camera_coll, context, 0.0, cam_clip_start, "_nad")
                if nad_result:
                    depth_objects += 1
                
                # Zlicz jako sukces jeśli cokolwiek zostało utworzone
                if section_result or widok_result or nad_result:
                    successful_objects += 1
                
            except Exception as e:
                continue
        
        # Raport końcowy
        elapsed_time = time.time() - start_time
        cache_info = get_cache_stats()
        success_msg = f"Aktualizacja w {elapsed_time:.1f}s. {successful_objects}/{total_objects} obj. {cache_info}"
        
        

        # Automatyczne czyszczenie cache po aktualizacji
        clear_bmesh_cache()
        
        # Aktualizuj właściwości fontów automatycznie
        font_updated_count = 0
        
        # Aktualizuj fonty powierzchni netto użytkowych
        for obj in bpy.data.objects:
            if (obj.type == 'FONT' and 
                obj.name.startswith("#Powierzchnia-netto-uzytkowa-text.") and 
                obj.data):
                
                # Sprawdź i zaktualizuj size
                target_size = 0.175953
                if abs(obj.data.size - target_size) > 0.001:
                    obj.data.size = target_size
                    font_updated_count += 1
                
                # Sprawdź i zaktualizuj font jeśli dostępny
                try:
                    if "Montserrat Thin" in bpy.data.fonts:
                        if obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                            obj.data.font = bpy.data.fonts["Montserrat Thin"]
                except:
                    pass
        
        # Aktualizuj fonty sum lokali
        import re
        for obj in bpy.data.objects:
            if obj.type == 'FONT' and obj.data:
                # Sprawdź czy to font sumy lokalu
                match = re.match(r'#Budynek\.([A-Z])_Lokal\.(\d+)', obj.name)
                if match:
                    # Sprawdź i zaktualizuj size
                    target_size = 0.219941
                    if abs(obj.data.size - target_size) > 0.001:
                        obj.data.size = target_size
                        font_updated_count += 1
                    
                    # Sprawdź i zaktualizuj font jeśli dostępny
                    try:
                        if "Montserrat Thin" in bpy.data.fonts:
                            if obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                                obj.data.font = bpy.data.fonts["Montserrat Thin"]
                        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                            for font in bpy.data.fonts:
                                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                                    if obj.data.font != font:
                                        obj.data.font = font
                                    break
                    except:
                        pass
        
        # Zastosuj Split by Loose Parts na obiektach MESH w kolekcji kamery
        split_count = 0
        objects_to_split = [obj for obj in camera_coll.objects if obj.type == 'MESH']
        
        for obj in objects_to_split:
            # Sprawdź czy obiekt ma więcej niż jedną wyspę geometrii
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            
            # Przejdź do trybu edycji
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Zaznacz wszystko
            bpy.ops.mesh.select_all(action='SELECT')
            
            # Użyj Split by Loose Parts
            try:
                result = bpy.ops.mesh.separate(type='LOOSE')
                if result == {'FINISHED'}:
                    split_count += 1
            except Exception as e:
                pass
            # Wróć do trybu obiektu
            bpy.ops.object.mode_set(mode='OBJECT')
        
        if split_count > 0:
            pass
        # Odznacz wszystkie obiekty
        bpy.ops.object.select_all(action='DESELECT')
        
        self.report({'INFO'}, success_msg)
        
        return {'FINISHED'}

class MIIXARCH_OT_SelectParent(Operator):
    bl_idname = "miixarch.select_parent"
    bl_label = "Select Parent"
    bl_description = "Zaznacza rodziców aktualnie zaznaczonych obiektów"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Operator działa tylko w trybie obiektu")
            return {'CANCELLED'}
        
        selected_objects = [obj for obj in context.selected_objects]
        if not selected_objects:
            self.report({'WARNING'}, "Brak zaznaczonych obiektów")
            return {'CANCELLED'}
        
        parents_to_select = []
        objects_without_parent = []
        
        # Znajdź rodziców zaznaczonych obiektów
        for obj in selected_objects:
            if obj.parent:
                if obj.parent not in parents_to_select:
                    parents_to_select.append(obj.parent)
            else:
                objects_without_parent.append(obj.name)
        
        if not parents_to_select:
            if objects_without_parent:
                self.report({'INFO'}, f"Żaden z {len(selected_objects)} zaznaczonych obiektów nie ma rodzica")
            return {'CANCELLED'}
        
        # Odznacz wszystkie obiekty
        bpy.ops.object.select_all(action='DESELECT')
        
        # Zaznacz rodziców
        for parent in parents_to_select:
            parent.select_set(True)
        
        # Ustaw ostatniego rodzica jako aktywny
        if parents_to_select:
            context.view_layer.objects.active = parents_to_select[-1]
        
        # Raport
        parent_count = len(parents_to_select)
        child_count = len(selected_objects) - len(objects_without_parent)
        
        if objects_without_parent:
            self.report({'INFO'}, 
                f"Zaznaczono {parent_count} rodziców dla {child_count} obiektów. "
                f"{len(objects_without_parent)} obiektów nie miało rodzica")
        else:
            self.report({'INFO'}, 
                f"Zaznaczono {parent_count} rodziców dla {child_count} obiektów")
        
        return {'FINISHED'}

class MIIXARCH_OT_UpdateFontProperties(Operator):
    bl_idname = "miixarch.update_font_properties"
    bl_label = "Aktualizuj właściwości fontów"
    bl_description = "Wymusza aktualizację właściwości fontów do wartości z kodu"

    def execute(self, context):
        updated_count = 0
        
        # Aktualizuj fonty powierzchni netto użytkowych
        for obj in bpy.data.objects:
            if (obj.type == 'FONT' and 
                obj.name.startswith("#Powierzchnia-netto-uzytkowa-text.") and 
                obj.data):
                
                # Sprawdź i zaktualizuj size
                target_size = 0.175953
                if abs(obj.data.size - target_size) > 0.001:
                    obj.data.size = target_size
                    updated_count += 1
                
                # Sprawdź i zaktualizuj font jeśli dostępny
                try:
                    if "Montserrat Thin" in bpy.data.fonts:
                        if obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                            obj.data.font = bpy.data.fonts["Montserrat Thin"]
                    elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                        for font in bpy.data.fonts:
                            if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                                if obj.data.font != font:
                                    obj.data.font = font
                                break
                except:
                    pass
        
        # Aktualizuj fonty sum lokali
        import re
        for obj in bpy.data.objects:
            if obj.type == 'FONT' and obj.data:
                # Sprawdź czy to font sumy lokalu
                match = re.match(r'#Budynek\.([A-Z])_Lokal\.(\d+)', obj.name)
                if match:
                    # Sprawdź i zaktualizuj size
                    target_size = 0.219941
                    if abs(obj.data.size - target_size) > 0.001:
                        obj.data.size = target_size
                        updated_count += 1
                    
                    # Sprawdź i zaktualizuj font jeśli dostępny
                    try:
                        if "Montserrat Thin" in bpy.data.fonts:
                            if obj.data.font != bpy.data.fonts["Montserrat Thin"]:
                                obj.data.font = bpy.data.fonts["Montserrat Thin"]
                        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
                            for font in bpy.data.fonts:
                                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                                    if obj.data.font != font:
                                        obj.data.font = font
                                    break
                    except:
                        pass
        
        self.report({'INFO'}, f"Zaktualizowano właściwości {updated_count} fontów")
        return {'FINISHED'}

def calculate_surface_area_by_category(area_number, category_names, name_filters=None):
    """
    Oblicza sumaryczną powierzchnię obiektów z określonych kolekcji w obszarze.
    
    Args:
        area_number: numer obszaru (str)
        category_names: lista nazw kolekcji do sprawdzenia (bez prefiksu #Obszar.X-)
        name_filters: lista filtrów nazw obiektów (opcjonalne)
    """
    total_area = 0.0
    
    for category in category_names:
        collection_name = f"#Obszar.{area_number}-{category}"
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            
            for obj in collection.objects:
                if obj.type == 'MESH':
                    # Sprawdź filtry nazw jeśli podane
                    if name_filters:
                        if not any(filter_name in obj.name for filter_name in name_filters):
                            continue
                    
                    # Pobierz powierzchnię z custom properties
                    if "Powierzchnia" in obj:
                        total_area += obj["Powierzchnia"]
                    elif "Powierzchnia razem" in obj:
                        total_area += obj["Powierzchnia razem"]
    
    return total_area

def calculate_surface_area_by_name_filter(area_number, name_filters):
    """Oblicza powierzchnię obiektów zawierających określone frazy w nazwie"""
    total_area = 0.0
    
    # Przeszukaj wszystkie kolekcje obszaru
    for collection in bpy.data.collections:
        if (collection.name.startswith(f'#Obszar.{area_number}-') and 
            'Legenda' not in collection.name):
            
            for obj in collection.objects:
                if obj.type == 'MESH':
                    # Sprawdź czy nazwa obiektu zawiera któryś z filtrów
                    if any(filter_name in obj.name for filter_name in name_filters):
                        # Pobierz powierzchnię z custom properties
                        if "Powierzchnia" in obj:
                            total_area += obj["Powierzchnia"]
                        elif "Powierzchnia razem" in obj:
                            total_area += obj["Powierzchnia razem"]
    
    return total_area

def format_number_pl(number):
    """Formatuje liczbę z przecinkiem jako separatorem dziesiętnym"""
    return f"{number:.2f}".replace('.', ',')

def get_area_collections():
    """Zwraca listę obszarów w formacie (numer, kolekcja)"""
    areas = []
    for collection in bpy.data.collections:
        if collection.name.startswith("#Obszar.") and "-" in collection.name:
            # Wyciągnij numer obszaru z nazwy, np. "#Obszar.1-Legenda" -> "1"
            try:
                area_number = collection.name.split(".")[1].split("-")[0]
                areas.append((area_number, collection))
            except (IndexError, ValueError):
                continue
    
    # Usuń duplikaty i sortuj
    unique_areas = {}
    for area_number, collection in areas:
        unique_areas[area_number] = collection
    
    return list(unique_areas.items())

def get_rain_gardens_data(area_number):
    """Pobiera dane wszystkich ogrodów deszczowych w obszarze"""
    gardens = []
    
    for collection in bpy.data.collections:
        if (collection.name.startswith(f'#Obszar.{area_number}-') and 
            'Legenda' not in collection.name):
            
            for obj in collection.objects:
                if obj.type == 'MESH' and obj.name.startswith('#Ogród_deszczowy'):
                    garden_data = {
                        'name': obj.name,
                        'surface': obj.get("Powierzchnia", 0.0),
                        'depth': obj.get("Głębokość", 0.0),
                        'volume': obj.get("Objętość", 0.0)
                    }
                    gardens.append(garden_data)
    
    return gardens

def generate_terrain_balance_text(area_number):
    """Generuje tekst bilansu terenu dla obszaru"""
    text_lines = []
    text_lines.append("BILANS TERENU")
    text_lines.append("")
    text_lines.append("Powierzchnia utwardzona:")
    
    # Klatki schodowe
    klatki_area = calculate_surface_area_by_category(area_number, ["Klatki_schodowe"])
    if klatki_area > 0:
        text_lines.append(f"  klatki schodowe: {format_number_pl(klatki_area)} m²")
    
    # Wiaty
    wiaty_area = calculate_surface_area_by_category(area_number, ["Wiaty"])
    if wiaty_area > 0:
        text_lines.append(f"  wiaty: {format_number_pl(wiaty_area)} m²")
    
    # Mury oporowe
    mury_area = calculate_surface_area_by_category(area_number, ["Mury"])
    if mury_area > 0:
        text_lines.append(f"  mury oporowe: {format_number_pl(mury_area)} m²")
    
    # Powierzchnie według materiałów
    categories = ["Drogi", "Chodniki", "Podjazdy", "Parkingi", "Tarasy"]
    materials = ["#Kostka_betonowa", "#Ekokrata", "#Kostka_farmerska", "#Deski_tarasowe"]
    
    total_hardened = klatki_area + wiaty_area + mury_area
    
    for category in categories:
        for material in materials:
            material_name = material.replace("#", "").replace("_", " ").lower()
            if material == "#Kostka_betonowa":
                material_name = "z kostki betonowej"
            elif material == "#Ekokrata":
                material_name = "z ekokraty"
            elif material == "#Kostka_farmerska":
                material_name = "z kostki farmerskiej"
            elif material == "#Deski_tarasowe":
                material_name = "z desek tarasowych"
            
            area = calculate_surface_area_by_category(area_number, [category], [material])
            if area > 0:
                text_lines.append(f"  {category.lower()} {material_name}: {format_number_pl(area)} m²")
                total_hardened += area
    
    text_lines.append("")
    text_lines.append(f"Razem powierzchnia utwardzona: {format_number_pl(total_hardened)} m²")
    
    return "\n".join(text_lines)

def generate_rain_balance_text(area_number):
    """Generuje tekst bilansu wód deszczowych dla obszaru"""
    text_lines = []
    text_lines.append("BILANS WÓD DESZCZOWYCH")
    text_lines.append("")
    text_lines.append("Wymagana objętość obiektów retencyjnych:")
    
    # Powierzchnia dachów - wsp. 1,0
    roofs_area = calculate_surface_area_by_name_filter(area_number, ["Dach"])
    if roofs_area > 0:
        text_lines.append(f"\tPowierzchnia dachów - wsp. 1,0: {format_number_pl(roofs_area)} m²")
    
    # Powierzchnie komunikacyjne szczelne - wsp. 1,0
    sealed_area = calculate_surface_area_by_name_filter(area_number, ["#Kostka_betonowa"])
    if sealed_area > 0:
        text_lines.append(f"\tPowierzchnie komunikacyjne szczelne - wsp. 1,0: {format_number_pl(sealed_area)} m²")
    
    # Powierzchnie komunikacyjne półprzepuszczalne - wsp. 0,5
    permeable_area = calculate_surface_area_by_name_filter(area_number, ["#Ekokrata"])
    permeable_weighted = permeable_area * 0.5
    if permeable_area > 0:
        text_lines.append(f"\tPowierzchnie komunikacyjne półprzepuszczalne - wsp. 0,5: {format_number_pl(permeable_area)} m² (= {format_number_pl(permeable_weighted)} m²)")
    
    # Skarpy - wsp. 0,25
    slopes_area = calculate_surface_area_by_category(area_number, ["Skarpy"])
    slopes_weighted = slopes_area * 0.25
    if slopes_area > 0:
        text_lines.append(f"\tSkarpy - wsp. 0,25: {format_number_pl(slopes_area)} m² (= {format_number_pl(slopes_weighted)} m²)")
    
    # Suma powierzchni ważonych
    total_weighted_area = roofs_area + sealed_area + permeable_weighted + slopes_weighted
    
    # Wymagana objętość - opad 30mm
    required_volume_30 = total_weighted_area * 0.03
    text_lines.append(f"  Wymagana objętość obiektów retencyjnych - opad 30 mm: {format_number_pl(required_volume_30)} m³")
    
    # Zalecana objętość - opad 60mm
    recommended_volume_60 = total_weighted_area * 0.06
    text_lines.append(f"  Zalecana objętość obiektów retencyjnych - opad 60 mm: {format_number_pl(recommended_volume_60)} m³")
    
    text_lines.append("")
    text_lines.append("Zestawienie projektowanej objętości obiektów retencyjnych:")
    
    # Ogrody deszczowe
    gardens = get_rain_gardens_data(area_number)
    
    # Sortuj ogrody numerycznie według numerów w nazwach
    def get_garden_number(garden):
        """Wyciąga numer z nazwy ogrodu deszczowego"""
        name = garden['name']
        try:
            # Próbuj wyciągnąć numer z końca nazwy (po ostatniej kropce)
            if '.' in name:
                num_str = name.split('.')[-1]
                return int(num_str)
            # Jeśli nie ma kropki, szukaj liczby w nazwie
            import re
            numbers = re.findall(r'\d+', name)
            if numbers:
                return int(numbers[-1])  # Weź ostatnią liczbę
        except (ValueError, IndexError):
            pass
        return 0  # Domyślnie 0 jeśli nie można wyciągnąć numeru
    
    gardens.sort(key=get_garden_number)
    total_garden_volume = 0.0
    
    for garden in gardens:
        garden_name = garden['name'].replace('#Ogród_deszczowy', 'Ogród deszczowy nr ')
        text_lines.append(f"  {garden_name}:")
        text_lines.append(f"    powierzchnia: {format_number_pl(garden['surface'])} m²")
        text_lines.append(f"    głębokość: {format_number_pl(garden['depth'])} m")
        text_lines.append(f"    objętość: {format_number_pl(garden['volume'])} m³")
        total_garden_volume += garden['volume']
    
    text_lines.append(f"  Całkowita objętość retencyjna ogrodów deszczowych: {format_number_pl(total_garden_volume)} m³")
    
    text_lines.append("")
    text_lines.append("Podsumowanie bilansu:")
    
    # Porównanie z wymaganiami
    if total_garden_volume >= recommended_volume_60:
        comparison = f"większa niż zalecana objętość obiektów retencyjnych ({format_number_pl(recommended_volume_60)} m³)"
    elif total_garden_volume >= required_volume_30:
        comparison = f"większa niż wymagana objętość obiektów retencyjnych ({format_number_pl(required_volume_30)} m³), ale mniejsza niż zalecana ({format_number_pl(recommended_volume_60)} m³)"
    else:
        comparison = f"mniejsza niż wymagana objętość obiektów retencyjnych ({format_number_pl(required_volume_30)} m³)"
    
    text_lines.append(f"  Całkowita objętość retencyjna ogrodów deszczowych ({format_number_pl(total_garden_volume)} m³) jest {comparison}")
    
    return "\n".join(text_lines)

def create_or_update_balance_text(area_number, balance_type, text_content):
    """Tworzy lub aktualizuje tekst bilansu"""
    text_name = f"{area_number}_BILANS_{balance_type}"
    
    # Sprawdź czy tekst już istnieje
    if text_name in bpy.data.texts:
        text_block = bpy.data.texts[text_name]
        text_block.clear()
        text_block.write(text_content)
    else:
        # Utwórz nowy tekst
        text_block = bpy.data.texts.new(text_name)
        text_block.write(text_content)
        text_block.use_fake_user = True

@persistent
def auto_export_layers_on_change(scene):
    """Automatycznie eksportuje warstwy do Text bloku przy każdej zmianie warstw"""
    try:
        if hasattr(scene, 'miixarch_dxf_layers') and len(scene.miixarch_dxf_layers) > 0:
            auto_export_layers_to_text()
    except Exception as e:
        # Ignoruj błędy w handlerze
                        pass

@persistent
def auto_import_layers_on_load(dummy):
    """Automatycznie importuje warstwy z Text bloku przy ładowaniu pliku"""
    try:
        scene = bpy.context.scene
        if hasattr(scene, 'miixarch_dxf_layers') and len(scene.miixarch_dxf_layers) == 0:
            # Próbuj zaimportować warstwy z Text bloku
            auto_import_layers_from_text()
    except Exception as e:
        # Ignoruj błędy w handlerze
                        pass

@persistent
def update_balance_texts(scene):
    """Automatycznie aktualizuje teksty bilansów dla wszystkich obszarów"""
    try:
        area_collections = get_area_collections()
        
        for area_number, collection in area_collections:
            # Generuj bilans terenu
            terrain_balance = generate_terrain_balance_text(area_number)
            create_or_update_balance_text(area_number, "TERENU", terrain_balance)
            
            # Generuj bilans wód deszczowych
            rain_balance = generate_rain_balance_text(area_number)
            create_or_update_balance_text(area_number, "DESZCZ", rain_balance)
            
    except Exception as e:
        print(f"Błąd podczas aktualizacji bilansów: {e}")

# -----------------------------------------------------------------------------
# Rejestracja -----------------------------------------------------------------
# -----------------------------------------------------------------------------

classes = (
    # PropertyGroups
    MIIXARCH_LayerProperty,
    # Operators
    MIIX_OT_update_drawing,
    MIIX_OT_export_drawing_layers,
    MIIX_OT_export_obszar_drawing,
    MIIXARCH_OT_AddLayer,
    MIIXARCH_OT_RemoveLayer,
    MIIXARCH_OT_InitializeDefaultLayers,
    MIIXARCH_OT_ExpandAllLayers,
    MIIXARCH_OT_CollapseAllLayers,
    MIIXARCH_OT_AssignDXFSettings,
    MIIXARCH_OT_CopyDXFSettings,
    MIIXARCH_OT_ExportLayersToText,
    MIIXARCH_OT_ImportLayersFromText,
    MIIXARCH_OT_ClearDXFCache,
    MIIXARCH_OT_ShowDXFCacheStats,
    MIIXARCH_OT_SetMaterialVisibility,
    MIIXARCH_OT_AssignSurface,
    MIIXARCH_OT_AssignObjectType,
    MIIXARCH_OT_GenerateContours,
    MIIXARCH_OT_CreateBuilding,
    MIIXARCH_OT_CreateArea,
    MIIXARCH_OT_UpdateBuilding,
    MIIXARCH_OT_UpdateArea,
    MIIXARCH_OT_SelectParent,
    MIIXARCH_OT_UpdateFontProperties,
    # Panels
    MIIXARCH_PT_ObszaryMainPanel,
    MIIXARCH_PT_ObszaryLayersPanel,
    MIIXARCH_PT_BudynkiMainPanel,
    MIIXARCH_PT_BudynkiLayersPanel,
    # Menus
    MIIXARCH_MT_LinkMenu,
)

# === FUNKCJE DLA OBIEKTÓW #OPIS-KOTA ===

@persistent
def update_kota_texts(scene):
    """Aktualizuje obiekty Font dla poziomów kota na podstawie globalnego położenia Z ich rodzica."""
    for text_obj in scene.objects:
        if (text_obj.type == 'FONT' and 
            text_obj.name.startswith('#Opis-kota-tekst.') and 
            text_obj.parent and 
            text_obj.parent.type == 'MESH' and
            text_obj.parent.name.startswith('#Opis-kota.')):
            
            # Pobierz globalne położenie Z rodzica
            parent = text_obj.parent
            global_z = parent.matrix_world.translation.z
            
            # Formatuj liczbę z dokładnością do 2 miejsc po przecinku
            # ze znakiem +/- i przecinkiem jako separatorem
            if global_z >= 0:
                formatted_z = f"+{global_z:.2f}".replace('.', ',')
            else:
                formatted_z = f"{global_z:.2f}".replace('.', ',')
            
            # Aktualizuj tekst jeśli się zmienił
            if text_obj.data and hasattr(text_obj.data, 'body'):
                if text_obj.data.body != formatted_z:
                    text_obj.data.body = formatted_z

@persistent
def auto_create_opis_kota_text_objects(scene):
    """Automatycznie tworzy obiekty Font dla obiektów Opis-kota, które ich nie mają."""
    for obj in scene.objects:
        if (obj.type == 'MESH' and 
            obj.name.startswith('#Opis-kota.') and
            len(obj.name.split('.')) == 2):  # Sprawdź że ma format #Opis-kota.XXX
            
            # Wyciągnij numer z nazwy obiektu
            try:
                suffix = obj.name.split('.')[-1]
                expected_text_name = f"#Opis-kota-tekst.{suffix}"
                
                # Sprawdź czy obiekt Font już istnieje
                text_obj = scene.objects.get(expected_text_name)
                if not text_obj:
                    # Sprawdź czy obiekt ma dziecko typu Font (może mieć inną nazwę)
                    has_font_child = any(child.type == 'FONT' and 
                                       child.name.startswith("#Opis-kota-tekst.") 
                                       for child in obj.children)
                    
                    if not has_font_child:
                        # Utwórz obiekt Font używając nowej funkcji
                        create_kota_text_object_standalone(obj, expected_text_name, bpy.context)
            except (ValueError, IndexError):
                # Ignoruj obiekty z nieprawidłową nazwą
                pass

def create_kota_text_object_standalone(kota_obj, text_name, context):
    """Tworzy obiekt Font dla obiektu kota - wersja standalone."""
    # Domyślny tekst (może być aktualizowany później)
    default_text = "+0,00"
    
    # Utwórz curve data
    curve_data = bpy.data.curves.new(name=text_name, type='FONT')
    curve_data.body = default_text
    curve_data.size = 0.175953  # Taki sam rozmiar jak surface font
    curve_data.use_fast_edit = True
    curve_data.align_x = 'CENTER'  # Wyśrodkowanie poziome
    curve_data.align_y = 'CENTER'  # Wyśrodkowanie pionowe
    
    # Ustaw font jeśli dostępny (taki sam jak w powierzchniach)
    try:
        if "Montserrat Thin" in bpy.data.fonts:
            curve_data.font = bpy.data.fonts["Montserrat Thin"]
        elif any("montserrat" in f.name.lower() and "thin" in f.name.lower() for f in bpy.data.fonts):
            for font in bpy.data.fonts:
                if "montserrat" in font.name.lower() and "thin" in font.name.lower():
                    curve_data.font = font
                    break
    except:
        pass  # Użyj domyślnego fontu
    
    # Utwórz obiekt
    text_obj = bpy.data.objects.new(text_name, curve_data)
    
    # Dodaj do tej samej kolekcji co rodzic
    for collection in kota_obj.users_collection:
        collection.objects.link(text_obj)
        break  # Dodaj tylko do pierwszej znalezionej kolekcji
    
    # Ustaw jako dziecko
    text_obj.parent = kota_obj
    text_obj.parent_type = 'OBJECT'
    
    # Umieść w środku bounding box rodzica (podobnie jak powierzchnie)
    bbox_center = sum((Vector(corner) for corner in kota_obj.bound_box), Vector()) / 8
    text_obj.location = bbox_center
    
    return text_obj

def register():
    for c in classes:
        bpy.utils.register_class(c)
    
    # NOTE: Menu functions (draw_miix_obszary_menu, etc.) are not implemented
    # Commenting out menu registration until functions are created
    
    # # Dodaj menu do panelu Add (tryb obiektu)
    # bpy.types.VIEW3D_MT_add.append(draw_miix_obszary_menu)
    # 
    # # Dodaj opcję Select Parent do menu Select
    # bpy.types.VIEW3D_MT_select_object.append(draw_select_parent_menu)
    # 
    # # Dodaj opcję Use edge as X axis do menu Edge
    # bpy.types.VIEW3D_MT_edit_mesh_edges.append(draw_edge_menu)
    # 
    # # Dodaj menu MIIX Tools do menu kontekstowego w trybie edycji
    # bpy.types.VIEW3D_MT_edit_mesh_context_menu.append(draw_miix_context_menu)
    # 
    # # Dodaj menu do panelu Add (tryb edycji mesh) - sprawdź czy istnieje
    # try:
    #     # Spróbuj różne nazwy menu dla trybu edycji
    #     if hasattr(bpy.types, 'VIEW3D_MT_edit_mesh_add'):
    #         bpy.types.VIEW3D_MT_edit_mesh_add.append(draw_miix_obszary_menu)
    #     elif hasattr(bpy.types, 'VIEW3D_MT_mesh_add'):
    #         bpy.types.VIEW3D_MT_mesh_add.append(draw_miix_obszary_menu)
    #     elif hasattr(bpy.types, 'VIEW3D_MT_add_mesh'):
    #         bpy.types.VIEW3D_MT_add_mesh.append(draw_miix_obszary_menu)
    # except:
    #     pass  # Jeśli nie ma menu dla trybu edycji, zignoruj
    
    # Właściwości z MIIX Architektura
    bpy.types.Scene.miixarch_surface_type = EnumProperty(
        name="Rodzaj",
        description="Wybierz rodzaj powierzchni",
        items=surface_types
    )
    bpy.types.Scene.miixarch_storeys = IntProperty(name="Liczba kondygnacji", default=1, min=1)
    bpy.types.Scene.miixarch_rename_target = StringProperty(name="Nazwa budynku lub obszaru", default="")
    bpy.types.Scene.miixarch_area_enum = EnumProperty(name="Obszar", items=get_area_items, update=update_rename_target_from_selection)
    bpy.types.Scene.miixarch_building_enum = EnumProperty(name="Budynek", items=get_building_items, update=update_rename_target_from_selection)
    bpy.types.Scene.miixarch_area_name = StringProperty(name="Nazwa obszaru", default="")
    bpy.types.Scene.miixarch_object_type = EnumProperty(name="Typ obiektu", items=get_object_type_items)
    bpy.types.Scene.miixarch_contour_unit = FloatProperty(name="Jednostka", default=1.0, min=0.001)
    
    # Właściwości DXF - kolekcja warstw
    bpy.types.Scene.miixarch_dxf_layers = CollectionProperty(type=MIIXARCH_LayerProperty)
    
    # Wyszukiwanie warstw
    bpy.types.Scene.miixarch_layer_search = StringProperty(
        name="Wyszukaj warstwę",
        description="Filtruj warstwy według nazwy",
        default=""
    )
    
    # UI controls dla ustawień DXF obiektów
    bpy.types.Scene.miixarch_selected_layer = EnumProperty(
        name="Warstwa DXF",
        description="Wybierz warstwę dla obiektu",
        items=get_layer_items
    )
    
    bpy.types.Scene.miixarch_ui_boundary_edges = BoolProperty(
        name="Krawędzie brzegowe",
        description="Eksportuj krawędzie brzegowe",
        default=True
    )
    
    bpy.types.Scene.miixarch_ui_internal_edges = BoolProperty(
        name="Krawędzie wewnętrzne", 
        description="Eksportuj krawędzie wewnętrzne",
        default=False
    )
    
    bpy.types.Scene.miixarch_ui_hatches = BoolProperty(
        name="Kreskowanie",
        description="Eksportuj kreskowanie",
        default=True
    )
    
    # NOTE: PropertyGroups zastąpione Custom Properties dla kompatybilności
    # Wszystkie ustawienia DXF przechowywane są teraz w obj["miix_dxf_*"]
    
    # Dodaj menu MIIX do Link/Transfer Data
    bpy.types.VIEW3D_MT_make_links.append(draw_miix_link_menu)

    # Handlery automatycznego przeliczania
    bpy.app.handlers.depsgraph_update_pre.append(secure_opis_poziom_positions)
    bpy.app.handlers.depsgraph_update_post.append(recalculate_area_on_edit)
    bpy.app.handlers.depsgraph_update_post.append(recalculate_area_object_properties_on_edit)
    bpy.app.handlers.depsgraph_update_post.append(recalculate_object_type_properties)
    bpy.app.handlers.depsgraph_update_post.append(recalculate_on_mode_change)
    bpy.app.handlers.depsgraph_update_post.append(auto_create_opis_spadek_text_objects)
    bpy.app.handlers.depsgraph_update_post.append(update_rzedna_texts)
    bpy.app.handlers.depsgraph_update_post.append(update_poziom_texts)
    bpy.app.handlers.depsgraph_update_post.append(update_spadek_texts)
    bpy.app.handlers.depsgraph_update_post.append(update_surface_text_objects)
    bpy.app.handlers.depsgraph_update_post.append(update_lokal_summary_text_objects)
    bpy.app.handlers.depsgraph_update_post.append(update_etykieta_rectangles)
    bpy.app.handlers.depsgraph_update_post.append(auto_create_etykieta_mesh_objects)
    bpy.app.handlers.depsgraph_update_post.append(update_ogrod_deszczowy_properties)
    bpy.app.handlers.depsgraph_update_post.append(auto_create_ogrod_deszczowy_labels)
    bpy.app.handlers.depsgraph_update_post.append(update_ogrod_deszczowy_labels)
    bpy.app.handlers.depsgraph_update_post.append(update_balance_texts)
    bpy.app.handlers.depsgraph_update_post.append(auto_export_layers_on_change)
    bpy.app.handlers.depsgraph_update_post.append(auto_create_opis_kota_text_objects)
    bpy.app.handlers.depsgraph_update_post.append(update_kota_texts)
    
    # Handler dla ładowania pliku
    bpy.app.handlers.load_post.append(auto_import_layers_on_load)


def unregister():
    # Usuń handlery
    if secure_opis_poziom_positions in bpy.app.handlers.depsgraph_update_pre:
        bpy.app.handlers.depsgraph_update_pre.remove(secure_opis_poziom_positions)
    if recalculate_area_on_edit in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(recalculate_area_on_edit)
    if recalculate_area_object_properties_on_edit in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(recalculate_area_object_properties_on_edit)
    if recalculate_object_type_properties in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(recalculate_object_type_properties)
    if recalculate_on_mode_change in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(recalculate_on_mode_change)
    if auto_create_opis_spadek_text_objects in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(auto_create_opis_spadek_text_objects)
    if update_rzedna_texts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_rzedna_texts)
    if update_poziom_texts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_poziom_texts)
    if update_spadek_texts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_spadek_texts)
    if update_surface_text_objects in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_surface_text_objects)
    if update_lokal_summary_text_objects in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_lokal_summary_text_objects)
    if update_etykieta_rectangles in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_etykieta_rectangles)
    if auto_create_etykieta_mesh_objects in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(auto_create_etykieta_mesh_objects)
    if update_ogrod_deszczowy_properties in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_ogrod_deszczowy_properties)
    if auto_create_ogrod_deszczowy_labels in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(auto_create_ogrod_deszczowy_labels)
    if update_ogrod_deszczowy_labels in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_ogrod_deszczowy_labels)
    if update_balance_texts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_balance_texts)
    if auto_export_layers_on_change in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(auto_export_layers_on_change)
    if auto_import_layers_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(auto_import_layers_on_load)
    if auto_create_opis_kota_text_objects in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(auto_create_opis_kota_text_objects)
    if update_kota_texts in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(update_kota_texts)

    
    # NOTE: Menu functions are commented out in register(), so also commenting out here
    
    # Usuń menu MIIX z Link/Transfer Data
    try:
        bpy.types.VIEW3D_MT_make_links.remove(draw_miix_link_menu)
    except:
        pass
    
    # # Usuń menu z panelu Add (tryb obiektu)
    # bpy.types.VIEW3D_MT_add.remove(draw_miix_obszary_menu)
    # 
    # # Usuń opcję Select Parent z menu Select
    # try:
    #     bpy.types.VIEW3D_MT_select_object.remove(draw_select_parent_menu)
    # except:
    #     pass
    # 
    # # Usuń opcję Use edge as X axis z menu Edge
    # try:
    #     bpy.types.VIEW3D_MT_edit_mesh_edges.remove(draw_edge_menu)
    # except:
    #     pass
    # 
    # # Usuń menu MIIX Tools z menu kontekstowego
    # try:
    #     bpy.types.VIEW3D_MT_edit_mesh_context_menu.remove(draw_miix_context_menu)
    # except:
    #     pass
    # 
    # # Usuń menu z panelu Add (tryb edycji mesh) - sprawdź czy istnieje
    # try:
    #     if hasattr(bpy.types, 'VIEW3D_MT_edit_mesh_add'):
    #         bpy.types.VIEW3D_MT_edit_mesh_add.remove(draw_miix_obszary_menu)
    #     elif hasattr(bpy.types, 'VIEW3D_MT_mesh_add'):
    #         bpy.types.VIEW3D_MT_mesh_add.remove(draw_miix_obszary_menu)
    #     elif hasattr(bpy.types, 'VIEW3D_MT_add_mesh'):
    #         bpy.types.VIEW3D_MT_add_mesh.remove(draw_miix_obszary_menu)
    # except:
    #     pass  # Jeśli nie ma menu dla trybu edycji, zignoruj
    
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()