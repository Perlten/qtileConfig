from typing import List
import os


from libqtile import bar, layout, widget, hook
import libqtile
from libqtile.backend.base import Window
from libqtile.config import Click, Drag, Group, Key, Match, Screen
from libqtile.core.manager import Qtile
from libqtile.group import _Group
from libqtile.lazy import lazy
from libqtile.utils import guess_terminal
from libqtile.log_utils import logger


from custom_widgets.ColoredGroupBox import ColoredGroupBox

from pymouse import PyMouse

import os
import subprocess

colors = {
    "net": ["#1D7EC6", "#1D7EC6"],  # net
    "wttr": ["#C6651D", "#C6651D"],  # wttr
    "cpu": ["#C6651D", "#C6651D"],  # cpu
    "memory": ["#1D7EC6", "#1D7EC6"],  # memory
    "df": ["#C61D7E", "#C61D7E"],  # DF
    "battery": ["#7EC61D", "#7EC61D"],  # battery
    "clock": ["#C61D29", "#C61D29"],  # clock
}


def print(data):
    logger.warning(data)


def create_screen_bar(visible_groups, show_systray=False):
    bootom_bar = [
        widget.Sep(),
        ColoredGroupBox(
            visible_groups=visible_groups,
            active=[
                ["#ff0000", "#00b0ff"],
                ["#ff0000", "#00ee00"],
                ["#00ff00", "#aaffaa"],
                ["#ffffff", "#0000ff"],
                ["#ff0000", "#ffffff"],
                ["#ff0000", "#0000ff"],
                ["#C6651D", "#00ff00"],
                ["#00ff00", "#ffffff"],
                ["#ffffff", "#0000ff"],
            ],
        ),
        widget.Sep(),
        widget.CurrentLayoutIcon(),
        widget.Sep(),
        widget.Prompt(),
        widget.Spacer(),
        widget.Sep(),
        widget.CPU(
            format="{freq_current}GHz {load_percent}%",
            foreground=colors["cpu"],
        ),
        widget.Sep(),
        widget.Memory(
            format="{MemUsed: .0f}{mm}/{MemTotal: .0f}{mm}",
            foreground=colors["memory"],
        ),
        widget.Sep(),
        widget.DF(
            visible_on_warn=False,
            format=" {f}/{s} GB",
            warn_space=50,
            foreground=colors["df"],
        ),
        widget.Sep(),
        widget.Battery(
            format="{percent:2.0%} {hour:d}:{min:02d}",
            foreground=colors["battery"],
            notify_below=20,
        ),
        widget.Sep(),
        widget.Clock(
            format=" %a %d-%m-%Y - %H:%M:%S",
            update_interval=5,
            foreground=colors["clock"],
        ),
    ]

    if show_systray:
        bootom_bar.append(widget.Sep())
        bootom_bar.append(widget.Systray(icon_size=40, padding=0))
    else:
        bootom_bar.append(
            widget.Spacer(length=12),
        )

    return Screen(
        top=bar.Bar(
            [
                widget.TaskList(
                    window_name_location=True,
                    highlight_method="block",
                    border="#243e80",
                    max_title_width=400,
                ),
                widget.Spacer(),
                widget.Net(format=" {down} ↓↑{up}", foreground=colors["net"]),
                widget.Sep(),
                widget.Wttr(
                    location={"Copenhagen": "Copenhagen"},
                    format="CPH:  %t  %c  %m  %p",
                    foreground=colors["wttr"],
                ),
            ],
            44,  # 44, 34
            background="#1f1d1dff",
        ),
        bottom=bar.Bar(bootom_bar, 44, background="#1f1d1dff"),  # 44, 34
    )


class PrevFocus(object):
    """Store last focus per group and go back when called"""

    def __init__(self):
        self.focus = None
        self.old_focus = None
        self.groups_focus = {}
        hook.subscribe.client_focus(self.on_focus)

    def on_focus(self, window):
        group = window.group
        # only store focus if the group is set
        if not group:
            return
        group_focus = self.groups_focus.setdefault(
            group.name, {"current": None, "prev": None}
        )

        if group_focus["current"] == window:
            return
        group_focus["prev"] = group_focus["current"]
        group_focus["current"] = window

    def __call__(self, qtile):
        group = qtile.current_group
        group_focus = self.groups_focus.get(group.name, {"prev": None})
        prev = group_focus["prev"]
        if prev and group.name == prev.group.name:
            group.focus(prev, False)
            center_if_layout_not_max(prev)


class PrevGroup(object):
    def __init__(self):
        self.previous_group_list = []
        hook.subscribe.client_focus(self.on_changegroup)

    def on_changegroup(self, window: Window):
        new_group = window.group
        if (
            len(self.previous_group_list) < 1
            or new_group != self.previous_group_list[-1]
        ):
            self.previous_group_list.append(new_group)

        if len(self.previous_group_list) > 2:
            self.previous_group_list.pop(0)

    def __call__(self, qtile):
        group_to_switch = self.previous_group_list[-2]
        switch_group_and_keep_screen_pos(group_to_switch)(qtile)


def center_if_layout_not_max(window: Window):
    layout_name = window.group.layout.name
    if layout_name != "max":
        info = window.info()
        center_mouse(info)


def center_mouse(position):
    width = position["width"]
    height = position["height"]
    x = position["x"]
    y = position["y"]

    m = PyMouse()
    x = x + (width // 2)
    y = y + (height // 2)
    m.move(x, y)


@libqtile.hook.subscribe.client_managed
def on_new_window(new_window: Window):
    order_windows_based_on_layout(new_window.group)


@libqtile.hook.subscribe.layout_change
def on_layout_change(_, current_group):
    order_windows_based_on_layout(current_group)


def change_window_position(qtile: Qtile, direction):
    current_layout = qtile.current_layout
    if direction == "left":
        current_layout.command("shuffle_left")()
    elif direction == "right":
        current_layout.command("shuffle_right")()
    elif direction == "up":
        current_layout.command("shuffle_up")()
    elif direction == "down":
        current_layout.command("shuffle_down")()

    order_windows_based_on_layout(qtile.current_group)


def order_windows_based_on_layout(current_group: _Group):
    current_layout = current_group.layout

    if current_layout.info().get("name") == "columns":
        window_list = current_group.windows
        columns = current_layout.info().get("columns")

        new_window_list = []

        for colum in columns:
            clients = colum.get("clients")
            for client_name in clients:
                window = [
                    window
                    for window in window_list
                    if window.name == client_name
                ][0]
                window_list.remove(window)
                new_window_list.append(window)
        print(new_window_list)
        current_group.windows = new_window_list


group_screen_index = [
    ["1", "2"],
    ["3", "4", "5", "6", "7", "8", "9"],
    [],
    [],
    [],
    [],
    [],
    [],
    [],
]


def switch_group_and_keep_screen_pos(group: Group):
    def _inner(qtile: Qtile):
        name = group.name

        if len(qtile.screens) == 1:
            pre_screen = qtile.current_screen
            qtile.groups_map[name].cmd_toscreen(toggle=False)

            if qtile.current_screen != pre_screen:
                center_mouse(qtile.current_screen.__dict__)

            group_screen_index[0].extend(group_screen_index[1])
            group_screen_index[1] = []
            return

        for index, screen_index_groups in enumerate(group_screen_index):
            if name in screen_index_groups:
                pre_screen = qtile.current_screen
                qtile.focus_screen(index)
                qtile.groups_map[name].cmd_toscreen(toggle=False)

                if qtile.current_screen != pre_screen:
                    center_mouse(qtile.current_screen.__dict__)

                break

    return _inner


def switch_group_screen(qtile: Qtile):
    name = qtile.current_group.name
    group = qtile.current_group

    for index, screen_index_groups in enumerate(group_screen_index):
        if name in screen_index_groups:
            name_index = screen_index_groups.index(name)
            screen_index_groups.pop(name_index)

            new_location = (index + 1) % len(qtile.screens)
            group_screen_index[new_location].append(name)

            redraw_all_screens(qtile)
            switch_group_and_keep_screen_pos(group)(qtile)
            break


def redraw_all_screens(qtile: Qtile):
    for screen in qtile.screens:
        getattr(screen, "top").draw()
        getattr(screen, "bottom").draw()


# ------------------------------------------------------


mod = "mod4"

# terminal = guess_terminal()
terminal = "terminator"

keys = [
    Key(
        [mod],
        "F12",
        lazy.spawn(
            "dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Next"
        ),
    ),
    Key(
        [mod],
        "F11",
        lazy.spawn(
            "dbus-send --print-reply --dest=org.mpris.MediaPlayer2.spotify /org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.Previous"
        ),
    ),
    Key([mod], "c", lazy.spawn("roficlip")),
    Key([mod, "control"], "m", lazy.spawn("pavucontrol")),
    Key([mod], "Escape", lazy.spawn("systemctl hibernate")),
    Key([mod], "l", lazy.spawn("betterlockscreen -l")),
    Key([mod], "b", lazy.function(switch_group_screen)),
    Key([], "XF86AudioRaiseVolume", lazy.spawn("amixer sset Master 5%+")),
    Key([], "XF86AudioLowerVolume", lazy.spawn("amixer sset Master 5%-")),
    Key([], "XF86AudioMute", lazy.spawn("amixer sset Master toggle")),
    Key([mod], "Down", lazy.layout.down(), desc="Move focus down"),
    Key([mod], "Up", lazy.layout.up(), desc="Move focus up"),
    Key([mod], "d", lazy.spawn("rofi -show run")),
    Key([mod], "p", lazy.spawn("rofi -show window")),
    Key([mod, "shift"], "Left", lazy.function(change_window_position, "left")),
    Key(
        [mod, "shift"], "Right", lazy.function(change_window_position, "right")
    ),
    Key([mod, "shift"], "Down", lazy.function(change_window_position, "down")),
    Key([mod, "shift"], "Up", lazy.function(change_window_position, "up")),
    Key([mod, "control"], "Left", lazy.layout.grow_left()),
    Key([mod, "control"], "Right", lazy.layout.grow_right()),
    Key(
        [mod, "control"],
        "Down",
        lazy.layout.grow_down(),
    ),
    Key([mod, "control"], "Up", lazy.layout.grow_up(), desc="Grow window up"),
    Key([mod], "n", lazy.layout.normalize(), desc="Reset all window sizes"),
    Key([mod], "Return", lazy.spawn(terminal), desc="Launch terminal"),
    # Toggle between different layouts as defined below
    Key([mod], "w", lazy.next_layout(), desc="Toggle between layouts"),
    Key([mod, "shift"], "q", lazy.window.kill(), desc="Kill focused window"),
    Key([mod, "control"], "r", lazy.reload_config(), desc="Reload the config"),
    Key(["mod1"], "Tab", lazy.function(PrevFocus())),
    Key([mod], "Tab", lazy.function(PrevGroup())),
    # Reservers menu bottom... its stupid
    Key([], "F24", lazy.function(lambda _: None)),
]

labels = [
    "",  # dev
    "",  # browser
    "",  # spotify
    "",  # terminal
    "",  # htop
    "",  # games
    "",  # paw print
    "",  # linux
    "",  # cog
]

groups = [Group(i, label=labels[int(i) - 1]) for i in "123456789"]

for index, i in enumerate(groups, 1):
    keys.extend(
        [
            Key(
                ["mod1"],
                i.name,
                lazy.function(
                    lambda q, index: (
                        center_if_layout_not_max(
                            q.current_group.windows[index - 1]),
                        q.cmd_switch_window(index),
                    ),
                    index,
                ),
            ),
            Key(
                ["mod1", "shift"],
                i.name,
                lazy.function(
                    lambda q, index: q.cmd_change_window_order(index), index),
            ),
            Key(
                [mod],
                i.name,
                lazy.function(switch_group_and_keep_screen_pos(i)),
                desc="Switch to group {}".format(i.name),
            ),
            Key(
                [mod, "shift"],
                i.name,
                lazy.window.togroup(i.name, switch_group=False),
                desc="Switch to & move focused window to group {}".format(
                    i.name
                ),
            ),
        ]
    )

layouts = [
    layout.Max(),
    layout.Columns(
        border_focus_stack=["#d75f5f", "#8f3d3d"], border_width=4, margin=6
    ),
]

widget_defaults = dict(
    font="sans",
    fontsize=26,  # 26, 18
    padding=6,
)

extension_defaults = widget_defaults.copy()


screens = [
    create_screen_bar(group_screen_index[0], True),
    create_screen_bar(group_screen_index[1]),
    create_screen_bar(group_screen_index[2]),
    create_screen_bar(group_screen_index[3]),
    create_screen_bar(group_screen_index[4]),
    create_screen_bar(group_screen_index[5]),
    create_screen_bar(group_screen_index[6]),
    create_screen_bar(group_screen_index[7]),
    create_screen_bar(group_screen_index[8]),
]


# Drag floating layouts.
mouse = [
    Drag(
        [mod],
        "Button1",
        lazy.window.set_position_floating(),
        start=lazy.window.get_position(),
    ),
    Drag(
        [mod],
        "Button2",
        lazy.window.set_size_floating(),
        start=lazy.window.get_size(),
    ),
    Click([mod], "Button3", lazy.window.toggle_floating()),
]

dgroups_key_binder = None
dgroups_app_rules = []  # type: List
follow_mouse_focus = True
bring_front_click = False
cursor_warp = False
floating_layout = layout.Floating(
    float_rules=[
        # Run the utility of `xprop` to see the wm class and name of an X client.
        *layout.Floating.default_float_rules,
        Match(wm_class="confirmreset"),  # gitk
        Match(wm_class="makebranch"),  # gitk
        Match(wm_class="maketag"),  # gitk
        Match(wm_class="ssh-askpass"),  # ssh-askpass
        Match(title="branchdialog"),  # gitk
        Match(title="pinentry"),  # GPG key password entry
    ]
)

auto_fullscreen = True
focus_on_window_activation = "smart"
reconfigure_screens = True

# If things like steam games want to auto-minimize themselves when losing
# focus, should we respect this or not?
auto_minimize = True


@hook.subscribe.startup_once
def start_once():
    if os.getenv("QTILE_NO_START_ONCE"):
        return
    auto = os.path.expanduser("~/.config/qtile/autostart.sh")
    subprocess.Popen([auto])


# XXX: Gasp! We're lying here. In fact, nobody really uses or cares about this
# string besides java UI toolkits; you can see several discussions on the
# mailing lists, GitHub issues, and other WM documentation that suggest setting
# this string if your java app doesn't work correctly. We may as well just lie
# and say that we're a working one by default.
#
# We choose LG3D to maximize irony: it is a 3D non-reparenting WM written in
# java that happens to be on java's whitelist.
wmname = "LG3D"


# software used
# lxappearance # for changing the theme
# autokey # for keybindings
# bmenu # for the menu (pointer speed and natural scrolling)
# trash-cli # for the trash
# oh_my_zsh # for the zsh shell
# oh_my_bash # for the bash shell
