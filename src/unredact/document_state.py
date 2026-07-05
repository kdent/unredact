class DocState:
    """
    DocState objects keep track of the state of various graphics elements in
    a PDF. Given a DocState object, the code can decide if a particular
    object is a redaction or not.
    """

    def __init__(
        self,
        rectangle_dimensions: list = None,
        color_space: str = "rg",
        fill_color: list = None,
    ) -> None:
        """
        Initialize a DocState object which tracks rectangle dimensions,
        fill color, and the current color space.
        """
        if rectangle_dimensions:
            self.rectangle_dimensions = rectangle_dimensions
        else:
            self.rectangle_dimensions = [0, 0, 0, 0]
        # The color space should be equal to "k" for CMYK, "rg" for RGB,
        # or "g" for greyscale
        self.color_space = color_space
        # The number of items in the fill_color list depends on the color
        # space value
        if fill_color:
            self.fill_color = fill_color
        else:
            self.fill_color = [0, 0, 0]

    def is_fill_color_white(self) -> bool:
        """
        Check if the current fill color is white.

        Since whiteness or transparency is different depending on the color
        space, the function determines if the current state fills objects
        with white.
        """
        white = False
        if self.color_space == "rg":
            if self.fill_color == [1, 1, 1]:
                white = True
        # CMYK is the opposite--absence of ink is white
        elif self.color_space == "k":
            if self.fill_color == [0, 0, 0, 0]:
                white = True
        # With grayscale 0.0 is black and 1.0 is white
        elif self.color_space == "g":
            if self.fill_color[0] == 1.0:
                white = True
        else:
            raise ValueError(
                f"The value: {self.color_space} is not valid for the "
                "color space"
            )
        return white

    def set_fill_color_white(self) -> None:
        """
        Set the current state to be 0 sized rectangle with white fill color.
        """
        if self.color_space == "rg":
            self.fill_color = [1, 1, 1]
        elif self.color_space == "k":
            self.fill_color = [0, 0, 0, 0]
        elif self.color_space == "g":
            self.fill_color = [0]
        else:
            raise ValueError(
                f"The value: {self.color_space} is not a valid for the "
                "color space"
            )

    def __str__(self) -> str:
        return (
            f"Rectangle Dimensions: {self.rectangle_dimensions}\n"
            f"Color Space: {self.color_space}\n"
            f"Fill Color: {self.fill_color}"
        )
