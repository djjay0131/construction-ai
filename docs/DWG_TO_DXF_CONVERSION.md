# Converting DWG Files to DXF

## Why DXF Instead of DWG?

**Phase 1 MVP currently supports DXF files only.** DWG is a proprietary binary format owned by Autodesk, while DXF (Drawing Exchange Format) is an open ASCII/binary format that's easier to parse.

**Good news:** Converting DWG to DXF is simple and free!

## Conversion Options

### Option 1: LibreCAD (Recommended - Free & Open Source)

1. **Download LibreCAD**
   - Visit: https://librecad.org/
   - Available for Windows, Mac, and Linux
   - Completely free

2. **Convert the File**
   - Open LibreCAD
   - File → Open → Select your .dwg file
   - File → Save As
   - Choose "AutoCAD DXF R2007" or "AutoCAD DXF R2013" format
   - Save with .dxf extension

### Option 2: FreeCAD (Free & Open Source)

1. **Download FreeCAD**
   - Visit: https://www.freecadweb.org/
   - Free CAD software with DWG import

2. **Convert the File**
   - Open FreeCAD
   - File → Open → Select your .dwg file
   - File → Export
   - Choose "AutoCAD DXF 2D" format
   - Save

### Option 3: Online Converters

**CloudConvert** (Free tier available)
- Visit: https://cloudconvert.com/dwg-to-dxf
- Upload your DWG file
- Select DXF as output format
- Download converted file

**Zamzar** (Free)
- Visit: https://www.zamzar.com/convert/dwg-to-dxf/
- Upload and convert

**Note:** Be mindful of file privacy when using online converters with sensitive architectural plans.

### Option 4: AutoCAD or DraftSight (Commercial)

If you have access to commercial CAD software:

**AutoCAD:**
- File → Save As → Select DXF format

**DraftSight:**
- File → Save As → DXF format

## Conversion Tips

1. **Use the latest DXF version** your converter supports (R2013, R2018, etc.)
2. **Check the file after conversion** - open in LibreCAD to verify
3. **Keep the original DWG** as a backup
4. **File size** - DXF files might be larger than DWG (this is normal)

## After Conversion

1. Navigate to http://localhost:5173
2. Upload your newly converted .dxf file
3. Configure parameters (wall height, stud spacing)
4. Click "Process Drawing"

## Example: HFH Sample Plan

The sample plan in `files/HFH 9557 Barnes Rd Prefab Plans.dwg` needs to be converted:

```bash
# Using LibreCAD (command line on Linux/Mac)
librecad -x "HFH 9557 Barnes Rd Prefab Plans.dwg" "HFH 9557 Barnes Rd Prefab Plans.dxf"
```

Or use the GUI method described above.

## Future Support

**Phase 2 will include:**
- Automatic DWG to DXF conversion
- ODA File Converter integration
- Support for all AutoCAD versions
- PDF and image file support

For now, manual conversion ensures maximum compatibility and allows Phase 1 MVP to focus on accurate material calculations!

## Need Help?

If you encounter issues with conversion:
1. Try a different converter (LibreCAD vs FreeCAD)
2. Check if the DWG file opens in LibreCAD first
3. Ensure the DWG file isn't corrupted
4. Check the file size (should be similar before/after conversion)

## Testing Your Converted File

After conversion, you can verify the DXF file:

1. **Open in LibreCAD** - should display the drawing
2. **Check layers** - ensure all layers are present
3. **Verify dimensions** - measurements should match original
4. **Test upload** - try uploading to Construction AI

---

**Once you have your DXF file, you're ready to get accurate material takeoffs!**
