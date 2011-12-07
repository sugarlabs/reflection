# -*- coding: utf-8 -*-
#Copyright (c) 2011 Walter Bender

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA


import gtk
import gobject

from random import uniform

from gettext import gettext as _

import logging
_logger = logging.getLogger('reflection-activity')

try:
    from sugar.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from sprites import Sprites, Sprite

# Grid dimensions must be even
TEN = 10
SIX = 6
DOT_SIZE = 40


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self._activity = parent
        self._colors = ['#FFFFFF']
        self._colors.append(colors[0])
        self._colors.append(colors[1])
        self._colors.append('#000000')

        self._canvas = canvas
        if parent is not None:
            parent.show_all()
            self._patent = parent

        self._canvas.set_flags(gtk.CAN_FOCUS)
        self._canvas.add_events(gtk.gdk.BUTTON_PRESS_MASK)
        self._canvas.connect("expose-event", self._expose_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)

        self._width = gtk.gdk.screen_width()
        self._height = gtk.gdk.screen_height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._width / (10 * DOT_SIZE * 1.2)
        self._dot_size = int(DOT_SIZE * self._scale)
        self._space = int(self._dot_size / 5.)
        self._orientation = 'horizontal'
        self.we_are_sharing = False

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self._dots = []
        for y in range(SIX):
            for x in range(TEN):
                xoffset = int((self._width - TEN * self._dot_size - \
                                   (TEN - 1) * self._space) / 2.)
                self._dots.append(
                    Sprite(self._sprites,
                           xoffset + x * (self._dot_size + self._space),
                           y * (self._dot_size + self._space),
                           self._new_dot(self._colors[0])))
                self._dots[-1].type = 0  # not set

        self.vline = Sprite(self._sprites,
                            int(self._width / 2.) - 1,
                            0, self._line(vertical=True))
        n = SIX / 2.
        self.hline = Sprite(
            self._sprites, 0,
            int(self._dot_size * n + self._space * (n - 0.5)) - 1,
            self._line(vertical=False))
        self.hline.hide()

        # and initialize a few variables we'll need.
        self._all_clear()

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''
        self._press = None
        self.saw_game_over = False

        # Clear dots
        for dot in self._dots:
            if dot.type > 0:
                dot.type = 0
                dot.set_shape(self._new_dot(self._colors[0]))

        self._set_orientation()

    def _set_orientation(self):
        ''' Set bar and message for current orientation '''
        if self._orientation == 'horizontal':
            self.hline.hide()
            self.vline.set_layer(1000)
        elif self._orientation == 'vertical':
            self.hline.set_layer(1000)
            self.vline.hide()
        else:
            self.hline.set_layer(1000)
            self.vline.set_layer(1000)

        if self._orientation == 'horizontal':
            self._set_label(
                _('Click on the dots to make a horizontal reflection.'))
        elif self._orientation == 'vertical':
            self._set_label(
                _('Click on the dots to make a vertical reflection.'))
        else:
            self._set_label(
                _('Click on the dots to make a bilateral reflection.'))

    def _initiating(self):
        return self._activity.initiating

    def new_game(self, orientation='horizontal'):
        ''' Start a new game. '''
        self._orientation = orientation

        self._all_clear()

        # Fill in a few dots to start
        for i in range(25):
            n = int(uniform(0, TEN * SIX))
            self._dots[n].type = int(uniform(0, 4))
            self._dots[n].set_shape(self._new_dot(
                    self._colors[self._dots[n].type]))

        if self.we_are_sharing:
            self._parent.send_new_game()

    def restore_game(self, dot_list, orientation):
        ''' Restore a game from the Journal or share '''
        for i, dot in enumerate(dot_list):
            self._dots[i].type = dot
            self._dots[i].set_shape(self._new_dot(
                    self._colors[self._dots[i].type]))
        self._set_orientation()

    def save_game(self):
        ''' Return dot list and orientation for saving to Journal or
        sharing '''
        dot_list = []
        for dot in self._dots:
            dot_list.append(dot.type)
        return (dot_list, self._orientation)

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        self._activity.status.set_label(string)

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = map(int, event.get_coords())

        spr = self._sprites.find_sprite((x, y), inverse=True)
        if spr == None:
            return

        if spr.type is not None:
            spr.type += 1
            spr.type %= 4
            spr.set_shape(self._new_dot(self._colors[spr.type]))
            self._test_game_over()

            if self.we_are_sharing:
                self._parent.send_dot_click(self._dots.index(spr),
                                            spr.type)
        return True

    def remote_button_press(self, dot, color):
        ''' Receive a button press from a sharer '''
        self._dots[dot].type = color
        self._dots.set_shape(self._new_dot(self._colors[color]))

    def set_sharing(self, share=True):
        self.we_are_sharing = share

    def _test_game_over(self):
        ''' Check to see if game is over '''
        if self._orientation == 'horizontal':
            for y in range(SIX):
                for x in range(SIX):
                    if self._dots[y * TEN + x].type != \
                            self._dots[y * TEN + TEN - x - 1].type:
                        self._set_label(_('keep trying'))
                        return False
            self._set_label(_('good work'))
            return True
        if self._orientation == 'vertical':
            for y in range(int(SIX / 2)):
                for x in range(TEN):
                    if self._dots[y * TEN + x].type != \
                            self._dots[(SIX - y - 1) * TEN + x].type:
                        self._set_label(_('keep trying'))
                        return False
            self._set_label(_('good work'))
        else:
            for y in range(SIX):
                for x in range(SIX):
                    if self._dots[y * TEN + x].type != \
                            self._dots[y * TEN + TEN - x - 1].type:
                        self._set_label(_('keep trying'))
                        return False
            for y in range(int(SIX / 2)):
                for x in range(TEN):
                    if self._dots[y * TEN + x].type != \
                            self._dots[(SIX - y - 1) * TEN + x].type:
                        self._set_label(_('keep trying'))
                        return False
            self._set_label(_('good work'))

    def _grid_to_dot(self, pos):
        ''' calculate the dot index from a column and row in the grid '''
        return pos[0] + pos[1] * TEN

    def _dot_to_grid(self, dot):
        ''' calculate the grid column and row for a dot '''
        return [dot % TEN, int(dot / SIX)]

    def game_over(self, msg=_('Game over')):
        ''' Nothing left to do except show the results. '''
        self._set_label(msg)
        self.saw_game_over = True

    def _expose_cb(self, win, event):
        self.do_expose_event(event)

    def do_expose_event(self, event):
        ''' Handle the expose-event by drawing '''
        # Restrict Cairo to the exposed area
        cr = self._canvas.window.cairo_create()
        cr.rectangle(event.area.x, event.area.y,
                event.area.width, event.area.height)
        cr.clip()
        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        gtk.main_quit()

    def _new_dot(self, color):
        ''' generate a dot of a color color '''
        self._dot_cache = {}
        if not color in self._dot_cache:
            self._stroke = color
            self._fill = color
            self._svg_width = self._dot_size
            self._svg_height = self._dot_size
            self._dot_cache[color] = svg_str_to_pixbuf(
                self._header() + \
                self._circle(self._dot_size / 2., self._dot_size / 2.,
                             self._dot_size / 2.) + \
                self._footer())
        return self._dot_cache[color]

    def _line(self, vertical=True):
        ''' Generate a center line '''
        if vertical:
            self._svg_width = 3
            self._svg_height = self._height
            return svg_str_to_pixbuf(
                self._header() + \
                self._rect(3, self._height, 0, 0) + \
                self._footer())
        else:
            self._svg_width = self._width
            self._svg_height = 3
            return svg_str_to_pixbuf(
                self._header() + \
                self._rect(self._width, 3, 0, 0) + \
                self._footer())

    def _header(self):
        return '<svg\n' + 'xmlns:svg="http://www.w3.org/2000/svg"\n' + \
            'xmlns="http://www.w3.org/2000/svg"\n' + \
            'xmlns:xlink="http://www.w3.org/1999/xlink"\n' + \
            'version="1.1"\n' + 'width="' + str(self._svg_width) + '"\n' + \
            'height="' + str(self._svg_height) + '">\n'

    def _rect(self, w, h, x, y):
        svg_string = '       <rect\n'
        svg_string += '          width="%f"\n' % (w)
        svg_string += '          height="%f"\n' % (h)
        svg_string += '          rx="%f"\n' % (0)
        svg_string += '          ry="%f"\n' % (0)
        svg_string += '          x="%f"\n' % (x)
        svg_string += '          y="%f"\n' % (y)
        svg_string += 'style="fill:#000000;stroke:#000000;"/>\n'
        return svg_string

    def _circle(self, r, cx, cy):
        return '<circle style="fill:' + str(self._fill) + ';stroke:' + \
            str(self._stroke) + ';" r="' + str(r - 0.5) + '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _footer(self):
        return '</svg>\n'


def svg_str_to_pixbuf(svg_string):
    """ Load pixbuf from SVG string """
    pl = gtk.gdk.PixbufLoader('svg')
    pl.write(svg_string)
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf
