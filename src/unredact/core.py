import copy

import pikepdf

from .document_state import DocState
from .state_stack import StateStack

UNREDACT_HIGHLIGHT_COLOR = [0.847, 0.749, 0.847]  # Thistle color
UNREDACT_HIGHLIGHT_PERCENTAGE = 0.5


class UnredactPdf:
    def __init__(self, pdf_obj):
        """
        Initialize a new object with a PDF file or file-like object
        """
        self.pdf_obj = pdf_obj
        self.pages = pdf_obj.pages

    @classmethod
    def from_path(cls, file_path):
        """
        Constructor to open a PDF file from a filepath

        Allow an exception to be thrown if the file is not available.
        """

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
        """
        Set up page resources and dictionary value for unredacted highlighting
        transparency.
        """
        # Ensure /Resources exists without destroying existing data
        if "/Resources" not in page:
            page["/Resources"] = pikepdf.Dictionary()

        # Ensure /ExtGState exists inside /Resources
        if "/ExtGState" not in page["/Resources"]:
            page["/Resources"]["/ExtGState"] = pikepdf.Dictionary()

        # Add or update the /SemiTransparent state safely
        page["/Resources"]["/ExtGState"]["/SemiTransparent"] = (
            pikepdf.Dictionary(
                {
                    "/Type": pikepdf.Name("/ExtGState"),
                    "/ca": percentage,  # Fill alpha (transparency)
                    "/CA": percentage,  # Stroke alpha
                                        # (good practice to include both)
                }
            )
        )

    def __is_graphics_state_transparent(self, page, gs_name):
        """
        Check the graphics state in the page to determine the opacity setting.

        In case the current graphics state is set to a transparent filling, we
        should ignore any rectangles that are drawn with a transparent fill.
        """
        transparent = False
        resources = page.get("/Resources", {})
        ext_gstate = resources.get("/ExtGState", {})
        if gs_name in ext_gstate:
            gs = ext_gstate[f"/{gs_name}"]
            if "/ca" in gs:  # lowercase = fill alpha
                if float(gs["/ca"]) == 0.0:
                    transparent = True

        return transparent

    def __calc_max_height(self, page):
        """
        Determine a maximum boundary for a potential redaction.

        Some rectangles are drawn for the entire page and should not be
        assumed to be redactions. This function figures out the height
        of 90% of the page under the assumption that the rectangle covers
        most or all of the page. Note that the 90% is chosen arbitrarily
        and might need to change based on more experience with real PDF
        files.
        """
        page_obj = page.obj
        # Extract visible boundary of page
        box = page_obj.Cropbox if "/Cropbox" in page_obj else page_obj.MediaBox
        height_pts = (
            box[3] - box[1]
        )  # Bounding boxes are formatted as:
           # lower_left_x, lower_left_y, upper_right_x, upper_right_y]

        # Calculate within 10% of the page bounding box
        return height_pts * 0.90

    def __is_redaction(self, current_state, page):
        """
        Determine if the current graphics object is a redaction or not
        """
        rect_height = current_state.rectangle_dimensions[3]
        max_height = self.__calc_max_height(page)
        if rect_height > pikepdf.Real(5) and rect_height < pikepdf.Real(
            max_height
        ):
            redaction = True
        else:
            redaction = False

        if redaction:
            if current_state.is_fill_color_white():
                redaction = False

        return redaction

    def process_page(self, page):
        """
        Process the provided PDF page.

        This function contains the primary processing loop that looks
        for redactions. It assumes that a redaction is created by drawing a
        PDF rectangle object. The loop processes a stream of PDF instructions
        looking for rectangles that might be redactions. It keeps track of
        various graphics state changes that are used to decide if a given
        rectangle should be treated as a redaction.

        The function also handles highlighting previously redacted text.
        """
        # This must run so the /SemiTransparent state is registered!
        self.__set_transparency_on_page(page, UNREDACT_HIGHLIGHT_PERCENTAGE)

        # TODO: check the page dictionary to see if there is any color
        # information already defined.
        current_state = DocState(
            rectangle_dimensions=[], fill_color=[0, 0, 0], color_space="rg"
        )
        graphics_state_history = StateStack()
        graphics_state_history.push(current_state)

        instructions = pikepdf.parse_content_stream(page)
        new_instructions = []

        for operands, operator in instructions:
            # If we encounter a fill (f) operator, check to see if it's a
            # redaction to be intercepted.
            if operator == pikepdf.Operator("f"):
                if self.__is_redaction(graphics_state_history.peek(), page):
                    # Inject transparent filling wrapped in state saves
                    new_instructions.append(([], pikepdf.Operator("q")))
                    new_instructions.append(
                        (UNREDACT_HIGHLIGHT_COLOR, pikepdf.Operator("rg"))
                    )

                    new_instructions.append(
                        (
                            [pikepdf.Name("/SemiTransparent")],
                            pikepdf.Operator("gs"),
                        )
                    )
                    new_instructions.append(([], pikepdf.Operator("f")))
                    new_instructions.append(([], pikepdf.Operator("Q")))
                else:
                    new_instructions.append((operands, operator))
                continue

            # Check for any instructions that affect the graphics state
            # which might influence a possible redaction. Most instructions
            # will cause an update to the current_state object.
            if operator == pikepdf.Operator("re"):
                current_state = graphics_state_history.peek()
                current_state.rectangle_dimensions = [
                    float(x) for x in operands
                ]
                # Dimensions can be negative reflecting relative direction.
                # Since we're concerned about the absolute size, we'll convert
                # the height dimension to its absolute value
                current_state.rectangle_dimensions[3] = abs(
                    current_state.rectangle_dimensions[3]
                )

            if operator == pikepdf.Operator("rg"):
                current_state = graphics_state_history.peek()
                current_state.color_space = "rg"
                current_state.fill_color = [float(x) for x in operands]
            if operator == pikepdf.Operator("k"):
                current_state = graphics_state_history.peek()
                current_state.color_space = "k"
                current_state.fill_color = [float(x) for x in operands]
            if operator == pikepdf.Operator("g"):
                current_state = graphics_state_history.peek()
                current_state.color_space = "g"
                current_state.fill_color = [float(x) for x in operands]

            if operator == pikepdf.Operator("cs"):
                current_state = graphics_state_history.peek()
                if operands == pikepdf.Name("/DeviceRGB"):
                    current_state.color_space = "rg"
                if operands == pikepdf.Name("/DeviceCMYK"):
                    current_state.color_space = "k"
                if operands == pikepdf.Name("/DeviceGray"):
                    current_state.color_space = "g"

            if operator == pikepdf.Operator(
                "sc"
            ) or operator == pikepdf.Operator("scn"):
                current_state = graphics_state_history.peek()
                # scn can have a trailing Name operand (for Pattern); skip it
                current_state.fill_color = [
                    x for x in operands if isinstance(x, float)
                ]

            # Graphics state may set opacity in the page dictionary
            if operator == pikepdf.Operator("gs"):
                if (
                    self.__is_graphics_state_transparent(page, str(operands))
                    == 1
                ):
                    current_state = graphics_state_history.peek()
                    current_state.set_fill_color_white()

            # Check for changes to the graphics stack (the q and Q operators).
            # PDF allows for graphics changes to take effect temporarily by
            # maintaining a graphics state. This code emulates the same
            # graphics state stack to simulate the same graphics state.
            if operator == pikepdf.Operator("q"):
                graphics_state = copy.deepcopy(graphics_state_history.peek())
                graphics_state_history.push(graphics_state)
            if operator == pikepdf.Operator("Q"):
                graphics_state_history.pop()

            # Keep everything else on the page intact (Text, Fonts,
            # layout structural paths)
            new_instructions.append((operands, operator))

        modified_stream_bytes = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pikepdf.Stream(self.pdf_obj, modified_stream_bytes)
