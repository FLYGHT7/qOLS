"""
Simple icon generator for qOLS plugin
Creates PNG icons to replace the default gray cubes with more intuitive icons
"""

import os
from PIL import Image, ImageDraw, ImageFont

def create_runway_icon(size=16):
    """Create a simple runway icon"""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Runway strip - dark gray
    runway_height = size // 3
    runway_y = (size - runway_height) // 2
    draw.rectangle([1, runway_y, size-1, runway_y + runway_height], 
                  fill=(74, 85, 104, 255), outline=(45, 55, 72, 255))
    
    # Centerline - white dashed
    center_y = size // 2
    for x in range(2, size-1, 3):
        draw.rectangle([x, center_y, x+1, center_y], fill=(255, 255, 255, 255))
    
    # Runway markings - white stripes
    for i in range(3):
        x = 3 + i * (size // 4)
        if x < size - 2:
            draw.rectangle([x, runway_y + 1, x + 1, runway_y + runway_height - 1], 
                          fill=(255, 255, 255, 255))
    
    return img

def create_threshold_icon(size=16):
    """Create a simple threshold icon"""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Runway base - light gray
    runway_height = size // 3
    runway_y = (size - runway_height) // 2
    draw.rectangle([1, runway_y, size-1, runway_y + runway_height], 
                  fill=(226, 232, 240, 255), outline=(74, 85, 104, 255))
    
    # Threshold area - red/white stripes
    threshold_width = size // 4
    for i in range(0, threshold_width, 2):
        color = (245, 101, 101, 255) if i % 4 == 0 else (255, 255, 255, 255)
        draw.rectangle([1 + i, runway_y, 1 + i + 1, runway_y + runway_height], 
                      fill=color)
    
    # Direction arrow - red
    arrow_size = size // 4
    arrow_y = runway_y - arrow_size
    points = [(size//2, arrow_y), 
              (size//2 + arrow_size//2, arrow_y + arrow_size), 
              (size//2 - arrow_size//2, arrow_y + arrow_size)]
    draw.polygon(points, fill=(245, 101, 101, 255))
    
    return img

def create_layer_icon(size=16):
    """Create a simple layer icon as fallback"""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Circle background
    draw.ellipse([1, 1, size-1, size-1], 
                fill=(189, 195, 199, 255), outline=(108, 117, 125, 255))
    
    # Layer lines
    for i in range(3):
        y = 4 + i * 3
        if y < size - 3:
            draw.line([(3, y), (size-3, y)], fill=(108, 117, 125, 255), width=1)
    
    return img

def generate_icons():
    """Generate all icon files"""
    icons_dir = os.path.join(os.path.dirname(__file__), 'icons')
    if not os.path.exists(icons_dir):
        os.makedirs(icons_dir)
    
    # Generate different sizes
    sizes = [16, 24, 32]
    
    for size in sizes:
        # Runway icon
        runway_img = create_runway_icon(size)
        runway_path = os.path.join(icons_dir, f'runway_icon_{size}.png')
        runway_img.save(runway_path, 'PNG')
        print(f"Created: {runway_path}")
        
        # Threshold icon
        threshold_img = create_threshold_icon(size)
        threshold_path = os.path.join(icons_dir, f'threshold_icon_{size}.png')
        threshold_img.save(threshold_path, 'PNG')
        print(f"Created: {threshold_path}")
        
        # Layer icon
        layer_img = create_layer_icon(size)
        layer_path = os.path.join(icons_dir, f'layer_icon_{size}.png')
        layer_img.save(layer_path, 'PNG')
        print(f"Created: {layer_path}")

if __name__ == "__main__":
    try:
        generate_icons()
        print("✅ All icons generated successfully!")
    except ImportError:
        print("❌ PIL (Pillow) not available. Icons will use fallback system.")
    except Exception as e:
        print(f"❌ Error generating icons: {e}")
