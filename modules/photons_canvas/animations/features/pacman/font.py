# Borrowed from https://github.com/devonbeckett/LifxTile2DEngine

from photons_canvas.font import Character, Space

from photons_canvas.canvas import CanvasColor


class PacmanCharacter(Character):
    colors = {
        "c": CanvasColor(207, 0.47, 0.14, 3500),  # cyan
        "y": CanvasColor(60, 1, 0.11, 3500),  # yellow
        "w": CanvasColor(0, 0, 0.3, 3500),  # white
        "p": CanvasColor(345, 0.25, 0.12, 3500),  # pink
        "o": CanvasColor(24, 1, 0.07, 3500),  # orange
        "r": CanvasColor(0, 1, 0.15, 3500),  # red
        "b": CanvasColor(240, 1, 0.15, 3500),  # blue
    }


PacmanR2LOpen = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        __yyyyyy
        ___yyyyy
        ____yyyy
        __yyyyyy
        _yyyyyy_
        __yyyy__
    """
)

PacmanClosed = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        yyyyyyyy
        yyyyyyyy
        yyyyyyyy
        yyyyyyyy
        _yyyyyy_
        __yyyy__
    """
)

PacmanL2ROpen = PacmanCharacter(
    """
        __yyyy__
        _yyyyyy_
        yyyyyy__
        yyyyy___
        yyyy____
        yyyyyy__
        _yyyyyy_
        __yyyy__
    """
)

Blinky = PacmanCharacter(
    """
        __rrrr__
        _rrrrrr_
        _wwrwwr_
        rbwrbwrr
        rrrrrrrr
        rrrrrrrr
        rrrrrrrr
        _r_rr_r_
    """
)

Pinky = PacmanCharacter(
    """
        __pppp__
        _pppppp_
        _wwpwwp_
        pbwpbwpp
        pppppppp
        pppppppp
        pppppppp
        _p_pp_p_
    """
)

Inky = PacmanCharacter(
    """
        __cccc__
        _cccccc_
        _wwcwwc_
        cbwcbwcc
        cccccccc
        cccccccc
        cccccccc
        _c_cc_c_
    """
)

Clyde = PacmanCharacter(
    """
        __oooo__
        _oooooo_
        _wwowwo_
        obwobwoo
        oooooooo
        oooooooo
        oooooooo
        _o_oo_o_
    """
)

Ghost = PacmanCharacter(
    """
        __bbbb__
        _bbbbbb_
        _bbwbwb_
        bbbwbwbb
        bbbbbbbb
        bwbwbwbb
        bbwbwbwb
        _b_bb_b_
    """
)

# Explicitly put Space in this context
# Mainly to make vim be quiet about it
Space = Space
