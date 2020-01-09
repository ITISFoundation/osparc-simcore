/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Theme.define("osparc.theme.Decoration", {
  extend: osparc.theme.osparcdark.Decoration,

  decorations: {

    "service-tree": {
      decorator: qx.ui.decoration.MSingleBorder,
      style: {
        width: 0
      }
    },

    "panelview": {
      style: {
        transitionProperty: "top",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "panelview-content": {
      style: {
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "outputPortHighlighted": {
      style: {
        backgroundColor: "background-main-lighter+"
      }
    },

    "window-small-cap": {
      include: "service-window",
      style: {
        width: 0,
        radius: 3,
        transitionProperty: "opacity",
        transitionDuration: "0.05s",
        transitionTimingFunction: "ease-in"
      }
    },

    "window-small-cap-maximized": {
      include: "service-window-maximized",
      style: {
        width: 0,
        transitionProperty: "opacity",
        transitionDuration: "0.05s",
        transitionTimingFunction: "ease-in"
      }
    },

    "workbench-small-cap-captionbar": {
      style: {
        width: 0
      }
    },

    "service-window": {
      include: "window",
      style: {
        radius: 3,
        width: 1
      }
    },

    "service-window-maximized": {
      include: "window",
      style: {
        width: 1
      }
    },

    "sidepanel": {
      style: {
        transitionProperty: ["left", "width"],
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "link-button": {},

    "service-browser": {
      style: {
        color: "material-button-background"
      }
    },

    "flash": {
      style: {
        radius: 3,
        transitionProperty: "top",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "flash-badge": {
      style: {
        radius: 5
      }
    },

    "flash-container-transitioned": {
      style: {
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "no-border": {
      style: {
        width: 0
      }
    },

    "border-editable": {
      style: {
        width: 1,
        radius: 3,
        color: "text-disabled"
      }
    },

    "hint": {
      style: {
        radius: 3
      }
    },

    "chip": {
      style: {
        radius: 9
      }
    },

    "pb-listitem": {
      style: {
        radius: 3
      }
    },

    "no-radius-button": {
      style: {
        radius: 0
      }
    },

    "tag": {
      style: {
        radius: 2
      }
    },
    "tagitem": {
      style: {
        radius: 2
      }
    },
    "tagitem-colorbutton": {
      include: "material-button",
      style: {
        radiusBottomRight: 0,
        radiusTopRight: 0
      }
    }
  }
});
