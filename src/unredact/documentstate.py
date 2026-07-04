

class DocState:
    def __init__(self, rectangle_dimensions, color_space, fill_color):
        self.rectangle_dimensions = []
        # The color space should be equal to "k" for CMYK, "rg" for RGB, or "g" for greyscale
        self.color_space = ""
        # The number of items in the fill_color list depends on the color space value
        self.fill_color = []


    def is_white(self):
        white = False
        if self.color_space == 'rg':
            if self.fill_color == [1, 1, 1]:
                white = True
        elif self.color_space == 'k':  # CMYK is the opposite--absence of ink is white
            if self.fill_color == [0, 0, 0, 0]:
                white = True
        elif self.color_space == 'g':
            if self.fill_color == [0]:
                white = True
        else:
            raise ValueError(f"The value: {self.color_space} is not valid for the color space")


