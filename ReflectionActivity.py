#Copyright (c) 2011 Walter Bender
#Copyright (c) 2012 Ignacio Rodriguez

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk,Gdk
from sugar3.activity import activity
from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton

from toolbar_utils import button_factory, label_factory, separator_factory, \
                          radio_factory
from utils import json_load, json_dump

import dbus
import logging

try:
    from sugar3.presence.wrapper import CollabWrapper
    logging.error('USING SUGAR COLLAB WRAPPER!')
except ImportError:
    from collabwrapper import CollabWrapper

from gettext import gettext as _

from game import Game

import logging
_logger = logging.getLogger('reflection-activity')


SERVICE = 'org.sugarlabs.ReflectionActivity'
IFACE = SERVICE
PATH = '/org/augarlabs/ReflectionActivity'


class ReflectionActivity(activity.Activity):
    ''' Reflection puzzle game '''

    def __init__(self, handle):
        ''' Initialize the toolbars and the game board '''
        try:
            super(ReflectionActivity, self).__init__(handle)
        except dbus.exceptions.DBusException as e:
            _logger.error(str(e))

        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']

        self._setup_toolbars()

        # Create a canvas
        canvas = Gtk.DrawingArea()
        canvas.set_size_request(Gdk.Screen.width(), \
                                Gdk.Screen.height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)
        self._setup_collab()
    
        if 'dotlist' in self.metadata:
            self._restore()
        else:
            self._game.new_game('horizontal')

    def _setup_toolbars(self):
        ''' Setup the toolbars. '''

        self.max_participants = 4

        toolbox = ToolbarBox()

        activity_button = ActivityToolbarButton(self)

        toolbox.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.set_toolbar_box(toolbox)
        toolbox.show()
        self.toolbar = toolbox.toolbar

        my_colors = radio_factory(
            'my-colors', self.toolbar, self._my_colors_cb, group=None)

        radio_factory('toolbar-colors', self.toolbar,
                      self._roygbiv_colors_cb, group=my_colors)

        self._new_game_button_h = button_factory(
            'new-game-horizontal', self.toolbar, self._new_game_cb,
            cb_arg='horizontal',
            tooltip=_('Start a new horizontal-reflection game.'))

        self._new_game_button_v = button_factory(
            'new-game-vertical', self.toolbar, self._new_game_cb,
            cb_arg='vertical',
            tooltip=_('Start a new vertical-reflection game.'))

        self._new_game_button_b = button_factory(
            'new-game-bilateral', self.toolbar, self._new_game_cb,
            cb_arg='bilateral',
            tooltip=_('Start a new bilateral-reflection game.'))

        self.status = label_factory(self.toolbar, '')

        separator_factory(toolbox.toolbar, False, True)

        self.robot_button = button_factory(
            'robot-off', self.toolbar, self._robot_cb,
            tooltip= _('Play with the robot.'))

        separator_factory(toolbox.toolbar, True, False)

        stop_button = StopButton(self)
        stop_button.props.accelerator = '<Ctrl>q'
        toolbox.toolbar.insert(stop_button, -1)
        stop_button.show()

    def _my_colors_cb(self, button=None):
        if hasattr(self, '_game'):
            self._game.roygbiv = False
            self._game.new_game()

    def _roygbiv_colors_cb(self, button=None):
        if hasattr(self, '_game'):
            self._game.roygbiv = True
            self._game.new_game()

    def _new_game_cb(self, button=None, orientation='horizontal'):
        ''' Start a new game. '''
        self._game.new_game(orientation)

    def _robot_cb(self, button=None):
        ''' Play with the computer (or not). '''
        if not self._game.playing_with_robot:
            self.set_robot_status(True, 'robot-on')
        else:
            self.set_robot_status(False, 'robot-off')

    def set_robot_status(self, status, icon):
        ''' Reset robot icon and status '''
        self._game.playing_with_robot = status
        self.robot_button.set_icon_name(icon)

    def write_file(self, file_path):
        ''' Write the grid status to the Journal '''
        [dot_list, orientation] = self._game.save_game()
        self.metadata['orientation'] = orientation
        self.metadata['dotlist'] = ''
        for dot in dot_list:
            self.metadata['dotlist'] += str(dot)
            if dot_list.index(dot) < len(dot_list) - 1:
                self.metadata['dotlist'] += ' '

    def _restore(self):
        ''' Restore the game state from metadata '''
        if 'orientation' in self.metadata:
            orientation = self.metadata['orientation']
        else:
            orientation = 'horizontal'

        dot_list = []
        dots = self.metadata['dotlist'].split()
        for dot in dots:
            dot_list.append(int(dot))
        self._game.restore_game(dot_list, orientation)

    # Collaboration-related methods

    def _setup_collab(self):
        ''' Setup the Collab Wrapper. '''
        self.initiating = None  # sharing (True) or joining (False)
        self._collab = CollabWrapper(self)
        self._collab.connect('message', self.__message_cb)

        owner = self._collab._leader
        self.owner = owner
        self._game.set_sharing(True)
        self._collab.setup()

    def __message_cb(self, collab, buddy, message):
        action = message.get('action')
        payload = message.get('payload')
        if action == 'n':
            '''Get a new game grid'''
            self._receive_new_game(payload)
        elif action == 'p':
            '''Get a dot click'''
            self._receive_dot_click(payload)

    def send_new_game(self):
        ''' Send a new orientation, grid to all players '''
        self._collab.post(dict(
                action = 'n',
                payload = json_dump(self._game.save_game())
            ))

    def _receive_new_game(self, payload):
        ''' Sharer can start a new game. '''
        [dot_list, orientation] = json_load(payload)
        self._game.restore_game(dot_list, orientation)

    def send_dot_click(self, dot, color):
        ''' Send a dot click to all the players '''
        self._collab.post(dict(
                action = 'p',
                payload = json_dump([dot, color])
            ))

    def _receive_dot_click(self, payload):
        ''' When a dot is clicked, everyone should change its color. '''
        (dot, color) = json_load(payload)
        self._game.remote_button_press(dot, color)

