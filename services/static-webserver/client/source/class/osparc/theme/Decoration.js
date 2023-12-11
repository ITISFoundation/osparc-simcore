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
  extend: osparc.theme.common.Decoration,

  decorations: {
    "material-button": {
      style: {
        radius: 4,
        backgroundColor: "material-button-background",
        transitionProperty: ["all"],
        transitionDuration: "0s",
        shadowColor: "transparent"
      }
    },

    "form-input": {
      style: {
        radius: [4, 4, 0, 0],
        width: [0, 0, 1, 0],
        style: "solid",
        color: "info"
      }
    },

    "form-password": {
      include: "form-input",
      style: {
        radius: 0,
        width: 0,
        backgroundColor: "transparent"
      }
    },

    "form-focus": {
      include: "form-input",
      style: {
        color: "success"
      }
    },

    "form-array-container": {
      style: {
        radius: 2,
        width: 1
      }
    },

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
        backgroundColor: "background-main-2"
      }
    },

    "window-small-cap": {
      include: "service-window",
      style: {
        shadowBlurRadius: 0,
        shadowLength: 0,
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

    "service-browser": {
      style: {
        color: "background-main-2"
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

    "flash-message": {
      style: {
        width: 1,
        style: "solid"
      }
    },

    "flash-info": {
      include: "flash-message",
      style: {
        color: "info"
      }
    },

    "flash-success": {
      include: "flash-message",
      style: {
        color: "success"
      }
    },

    "flash-warning": {
      include: "flash-message",
      style: {
        color: "warning"
      }
    },

    "flash-error": {
      include: "flash-message",
      style: {
        color: "error"
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
        radius: 4,
        width: 1,
        color: "transparent"
      }
    },

    "border-status": {
      decorator: qx.ui.decoration.MSingleBorder,
      style: {
        width: 1
      }
    },

    "border-ok": {
      include: "border-status",
      style: {
        color: "ready-green"
      }
    },

    "border-warning": {
      include: "border-status",
      style: {
        color: "warning-yellow"
      }
    },

    "border-error": {
      include: "border-status",
      style: {
        color: "failed-red"
      }
    },

    "border-busy": {
      include: "border-status",
      style: {
        color: "busy-orange"
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
        radius: 5
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
    },
    "tagbutton": {
      include: "material-button",
      style: {
        backgroundColor: "transparent",
        shadowColor: "transparent",
        radius: 0
      }
    },
    "bordered-button": {
      include: "material-button",
      style: {
        width: 1,
        color:  "background-main-4"
      }
    },
    "strong-bordered-button": {
      include: "material-button",
      style: {
        width: 1,
        color: "text"
      }
    },
    "form-button": {
      style: {
        style: "solid",
        width: 1,
        color: "default-button",
        radius: 5
      }
    },
    "form-button-outlined": {
      include: "form-button",
      style: {
        color: "default-button",
        backgroundColor: "transparent"
      }
    },
    "form-button-danger": {
      include:"form-button-outlined",
      style: {
        color: "error",
        width: 1,
        style: "solid"
      }
    },
    "form-button-danger-hover": {
      include:"form-button-outlined",
      style: {
        color: "error",
        width: 1,
        style: "solid"
      }
    },
    "form-button-hover": {
      include: "form-button",
      style: {
        color: "default-button-hover",
        backgroundColor: "default-button-hover-background"
      }
    },
    "form-button-focus": {
      include: "form-button",
      style: {
        color: "default-button-focus",
        backgroundColor: "default-button-focus"
      }
    },
    "form-button-active": {
      include: "form-button",
      style: {
        color: "default-button-active"
      }
    },
    "form-button-disabled": {
      include: "form-button",
      style: {
        color: "transparent"
      }
    },
    "text-button": {
      style: {
        width: 0,
        radius: 0
      }
    },

    "toolbar-button": {
      include: "form-button-outlined",
      style: {
        backgroundColor: "default-button"
      }
    },

    "toolbar-button-hovered": {
      include: "form-button-outlined",
      style: {
        backgroundColor: "default-button-hover-background"
      }
    },

    "fab-button": {
      include: "form-button",
      style: {
        width: 1,
        color: "transparent",
        backgroundColor: "background-card-overlay"
      }
    }
  }
});
