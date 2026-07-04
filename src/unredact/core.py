#!/usr/bin/env python3

import pathlib
import pikepdf
import sys

UNREDACT_HIGHLIGHT_COLOR = [0.847, 0.749, 0.847]  # Thistle color
UNREDACT_HIGHLIGHT_PERCENTAGE = 0.5


def get_output_filename(input_filepath):
    """Retrieve the output file name."""
    file_path = pathlib.Path(input_filepath)
    return str(
        file_path.with_name(file_path.stem + "-unredacted" + file_path.suffix)
    )


def set_transparency_on_page(page, percentage):
    '''
        Set up page resources and dictionary value for unredacted highlighting transparency.
    '''
    # 1. Ensure /Resources exists without destroying existing data
    if "/Resources" not in page:
        page.Resources = pikepdf.Dictionary()
    
    resources = page.Resources

    # 2. Ensure /ExtGState exists inside /Resources
    if "/ExtGState" not in resources:
        resources.ExtGState = pikepdf.Dictionary()
        
    ext_g_state = resources.ExtGState

    # 3. Add or update the /SemiTransparent state safely
    ext_g_state["/SemiTransparent"] = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/ExtGState"),
        "/ca": percentage,  # Fill alpha (transparency)
        "/CA": percentage   # Stroke alpha (good practice to include both)
    })


def get_max_height(page):
    page_obj = page.obj
    # Extract visible boundary of page
    box = page_obj.Cropbox if "/Cropbox" in page_obj else page_obj.MediaBox
    height_pts = box[3] - box[1]  # Bounding boxes are formatted as: [lower_left_x, lower_left_y, upper_right_x, upper_right_y]

    # Calculate within 10% of the page bounding box
    return height_pts * 0.90


def is_redaction(current_state):
    '''Contains the logic to decide if the current graphics object is a redaction or not'''

    print("checking is redaction with dimensions", current_state['rectangle_dimensions'])
    rect_height = current_state['rectangle_dimensions'][3]
    max_height = get_max_height(page)
    if rect_height > pikepdf.Real(5) and rect_height < pikepdf.Real(max_height):
        redaction = True
    else:
        redaction = False
    return redaction

def process_page(pdf, page):
    # CRITICAL: This must run so the /SemiTransparent state is registered!
    set_transparency_on_page(page, UNREDACT_HIGHLIGHT_PERCENTAGE)

    current_state = {
        'fill_color': [1, 1, 1],
        'rectangle_dimensions': []
    }
    
    instructions = pikepdf.parse_content_stream(page)
    new_instructions = []
    
    # Use a local boolean flag to track if the *immediate previous instruction* was a target rectangle
    possible_redaction = False
    fill_color_is_blank = False

    # Iterate through the instructions to filter out the drawing shapes
    for operands, operator in instructions:
 
        if operator == pikepdf.Operator('re'):
            current_state['rectangle_dimensions'] = list(operands)
            new_instructions.append((operands, operator))
            continue
 
        # If it's the fill command belonging to a targeted rectangle
        if operator == pikepdf.Operator('f'):
            if is_redaction(current_state):
                print("filling ")
                # Inject transparent filling wrapped in state saves
                new_instructions.append(([], pikepdf.Operator('q')))
                new_instructions.append((UNREDACT_HIGHLIGHT_COLOR, pikepdf.Operator('rg')))

                new_instructions.append(([pikepdf.Name('/SemiTransparent')], pikepdf.Operator('gs')))
                new_instructions.append(([], pikepdf.Operator('f')))
                new_instructions.append(([], pikepdf.Operator('Q')))
            else:
                print("not gonna fill")
                new_instructions.append((operands, operator))

            current_state = {
                'fill_color': [],
                'rectangle_dimensions': []
            }
            continue

#        if operator == pikepdf.Operator('rg'):
#            if operands[0] == pikepdf.Real(0) and operands[1] == pikepdf.Real(0) and operands[2] == pikepdf.Real(0):
#                fill_color_is_blank = True
#                print("with operands", operands, "setting blank")
#            else:
#                fill_color_is_blank = False
#                print("with operands", operands, "not setting blank")

#        if operator == pikepdf.Operator('Q'):   # TODO: fix logic to keep track of the state
#            fill_color_is_blank = False

#   Also check CMYK (k) and greyscale color space changes


        # FIX: Keep everything else on the page intact (Text, Fonts, layout structural paths)
        new_instructions.append((operands, operator))
        possible_redaction = False

    modified_stream_bytes = pikepdf.unparse_content_stream(new_instructions)
    page.Contents = pikepdf.Stream(pdf, modified_stream_bytes)



if __name__ == "__main__":

    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {sys.argv[0]} <pdf_file>\n")
        sys.exit(1)

    pdf_file = sys.argv[1]
    output_pdf = get_output_filename(pdf_file)

    # Open the PDF
    pdf = pikepdf.open(pdf_file)

    for page in pdf.pages:
        process_page(pdf, page)

    # Changed from hardcoded filename to your calculated output_pdf path variable
    pdf.save('pikepdf_unredacted.pdf')
#    pdf.save(output_pdf)
#    print(f"Saved changes to: {output_pdf}")
