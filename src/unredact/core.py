
import os
import pikepdf
from .documentstate import DocState

UNREDACT_HIGHLIGHT_COLOR = [0.847, 0.749, 0.847]  # Thistle color
UNREDACT_HIGHLIGHT_PERCENTAGE = 0.5


class UnredactPdf:
    def __init__(self, pdf_obj):
        """
        Initialize a new object with a PDF file-like object
        """
        self.pdf_obj = pdf_obj
        self.pages = pdf_obj.pages


    @classmethod
    def from_path(cls, file_path):
        """
        Constructor to open a PDf file from a filepath
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No file found at {file_path}")

        # Open the file
        pdf = pikepdf.open(file_path)
        return cls(pdf)


    def save(self, target):
        """
        Save the unredacted file content.
        
        Accepts a file-like object (with a .write() method) OR a string path.
        """
        self.pdf_obj.save(target)


    def __set_transparency_on_page(self, page, percentage):
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


    def __calc_max_height(self, page):
        page_obj = page.obj
        # Extract visible boundary of page
        box = page_obj.Cropbox if "/Cropbox" in page_obj else page_obj.MediaBox
        height_pts = box[3] - box[1]  # Bounding boxes are formatted as: [lower_left_x, lower_left_y, upper_right_x, upper_right_y]

        # Calculate within 10% of the page bounding box
        return height_pts * 0.90


    def __is_redaction(self, current_state, page):
        '''
        Determine if the current graphics object is a redaction or not
        '''
        print("checking is redaction with dimensions", current_state.rectangle_dimensions)
        rect_height = current_state.rectangle_dimensions[3]
        max_height = self.__calc_max_height(page)
        if rect_height > pikepdf.Real(5) and rect_height < pikepdf.Real(max_height):
            redaction = True
        else:
            redaction = False

        if redaction:
            if current_state.is_white():
                redaction = False
 
        return redaction


    def process_page(self, page):
        # CRITICAL: This must run so the /SemiTransparent state is registered!
        self.__set_transparency_on_page(page, UNREDACT_HIGHLIGHT_PERCENTAGE)

        # TODO: check the page dictionary to see if there is any color information
        current_state = DocState(rectangle_dimensions=[], fill_color=[0, 0, 0], color_space='rg')
        
        instructions = pikepdf.parse_content_stream(page)
        new_instructions = []
        
        # Use a local boolean flag to track if the *immediate previous instruction* was a target rectangle
        possible_redaction = False
        fill_color_is_blank = False

        # Iterate through the instructions to filter out the drawing shapes
        for operands, operator in instructions:
    
            if operator == pikepdf.Operator('re'):
                current_state.rectangle_dimensions = list(operands)
                new_instructions.append((operands, operator))
                continue
    
            # If it's the fill command belonging to a targeted rectangle
            if operator == pikepdf.Operator('f'):
                if self.__is_redaction(current_state, page):
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
                continue

            if operator == pikepdf.Operator('rg'):
                current_state.color_space = 'rg'
                current_state.fill_color = [float(x) for x in operands]
                print("setting fill color to", current_state.fill_color)

    #        if operator == pikepdf.Operator('Q'):   # TODO: fix logic to keep track of the state
    #            fill_color_is_blank = False

    #   Also check CMYK (k) and greyscale color space changes


            # FIX: Keep everything else on the page intact (Text, Fonts, layout structural paths)
            new_instructions.append((operands, operator))
            possible_redaction = False

        modified_stream_bytes = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pikepdf.Stream(self.pdf_obj, modified_stream_bytes)


