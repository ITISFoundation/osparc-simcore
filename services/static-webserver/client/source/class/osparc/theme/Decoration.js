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
    "rounded": {
      style: {
        radius: 4
      }
    },

    "border-simple": {
      include: "border",
      style: {
        radius: 4
      }
    },

    "no-border": {
      style: {
        radius: 4,
        width: 1,
        color: "transparent"
      }
    },

    "material-button-invalid": {},
    "material-button": {
      style: {
        radius: 4,
        backgroundColor: "material-button-background",
        transitionProperty: ["background-color", "border-color", "opacity"],
        transitionDuration: "0.25s",
        transitionTimingFunction: "linear",
        shadowColor: "transparent"
      }
    },

    "indicator-border": {
      include: "material-button",
      style: {
        radius: 4,
        width: 1,
        color: "text"
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

    "form-input-focused": {
      include: "form-input",
      style: {
        color: "product-color"
      }
    },

    "form-input-disabled": {
      include: "form-input",
      style: {
        color: "text-disabled"
      }
    },

    "form-input-invalid": {
      include: "form-input",
      style: {
        color: "error"
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

    "node-ui-cap": {
      include: "service-window",
      style: {
        shadowBlurRadius: 0,
        shadowLength: 0,
        width: 0,
        radius: 4,
        transitionProperty: "opacity",
        transitionDuration: "0.05s",
        transitionTimingFunction: "ease-in"
      }
    },

    "node-ui-cap-maximized": {
      include: "service-window-maximized",
      style: {
        width: 1,
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
        radius: 4,
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
        radius: 4,
        transitionProperty: "top",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "flash-message": {
      style: {
        radius: 4,
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
        radius: 4
      }
    },

    "flash-container-transitioned": {
      style: {
        transitionProperty: "height",
        transitionDuration: "0.2s",
        transitionTimingFunction: "ease-in"
      }
    },

    "no-border-2": {
      style: {
        width: 0
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
        radius: 4,
        color: "text-disabled"
      }
    },

    "hint": {
      style: {
        radius: 4
      }
    },

    "chip": {
      style: {
        radius: 4
      }
    },

    "chip-button": {
      style: {
        width: 1,
        radius: 4,
        color: "text",
        backgroundColor: "transparent"
      }
    },

    "filter-toggle-button": {
      style: {
        width: 1,
        radius: 4,
        color: "transparent"
      }
    },

    "filter-toggle-button-selected": {
      include: "filter-toggle-button",
      style: {
        color: "text"
      }
    },

    "pb-listitem": {
      style: {
        radius: 4
      }
    },

    "pb-locked": {
      style: {
        backgroundColor: "pb-locked"
      }
    },

    "no-radius-button": {
      style: {
        radius: 0
      }
    },

    "tag": {
      style: {
        radius: 4
      }
    },
    "tagitem": {
      style: {
        radius: 4
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
    "tab-button": {
      style: {
        style: "solid",
        width: [0, 0, 2, 0],
        color: "transparent",
        radius: [4, 4, 0, 0]
      }
    },
    "tab-button-selected": {
      style: {
        style: "solid",
        width: [0, 0, 2, 0],
        color: "default-button-focus",
        radius: [4, 4, 0, 0]
      }
    },

    // Button types
    "form-button": {
      include: "material-button",
      style: {
        style: "solid",
        width: 1,
        color: "default-button",
        radius: 4,
        backgroundColor: "default-button"
      }
    },
    "fab-button": {
      include: "form-button",
      style: {
        style: "solid",
        width: 1,
        radius: 4,
        color: "fab-background",
        backgroundColor: "fab-background",
        shadowSpreadRadius: 0,
        shadowBlurRadius: 3,
        shadowLength: 0,
        shadowColor: "box-shadow"
      }
    },
    "form-button-outlined": {
      include: "form-button",
      style: {
        color: "default-button",
        backgroundColor: "default-button-background"
      }
    },
    "form-button-text": {
      style: {
        width: 0,
        radius: 0,
        color: null,
        backgroundColor: null
      }
    },

    // Button States
    "form-button-hovered": {
      include: "form-button",
      style: {
        color: "default-button-hover",
        backgroundColor: "default-button-hover-background"
      }
    },
    "form-button-hovered-checked": {
      include: "form-button",
      style: {
        color: "default-button-disabled",
        backgroundColor: "default-button"
      }
    },
    "form-button-checked": {
      include: "form-button",
      style: {
        color: "default-button-disabled",
        backgroundColor: "default-button-disabled-background"
      }
    },
    "form-button-focused": {
      include: "form-button",
      style: {
        color: "default-button-focus",
        backgroundColor: "default-button-focus-background"
      }
    },
    "form-button-active": {
      include: "form-button",
      style: {
        color: "default-button-active",
        backgroundColor: "default-button-focus-background"
      }
    },
    "form-button-disabled": {
      include: "form-button",
      style: {
        color: "transparent",
        backgroundColor: "transparent"
      }
    },

    // Split buttons
    // Middle
    "form-button-outlined-middle": {
      include: "form-button-outlined",
      style: {
        width: [1, 0],
        radius: 0
      }
    },

    // Right
    "form-button-outlined-right": {
      include: "form-button-outlined",
      style: {
        width: [1, 1, 1, 1],
        radius: [0, 4, 4, 0]
      }
    },
    "form-button-outlined-hovered-right": {
      include: "form-button-outlined-right",
      style: {
        color: "default-button-hover",
        backgroundColor: "default-button-hover-background"
      }
    },
    "form-button-outlined-checked-right": {
      include: "form-button-outlined-right",
      style: {
        color: "default-button",
        backgroundColor: "default-button"
      }
    },

    // Left
    "form-button-outlined-left": {
      include: "form-button-outlined",
      style: {
        width: [1, 0, 1, 1],
        radius: [4, 0, 0, 4]
      }
    },
    "form-button-outlined-hovered-left": {
      include: "form-button-outlined-left",
      style: {
        color: "default-button-hover",
        backgroundColor: "default-button-hover-background"
      }
    },
    "form-button-outlined-checked-left": {
      include: "form-button-outlined-left",
      style: {
        color: "default-button",
        backgroundColor: "default-button"
      }
    },

    // Delete button
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

    "toolbar-button": {
      include: "form-button-outlined"
    },

    "toolbar-button-hovered": {
      include: "form-button-outlined",
      style: {
        backgroundColor: "default-button-hover-background"
      }
    },

    "selected-light": {
      include: "material-button",
      style: {
        style: "solid",
        width: 1,
        color: "background-selected-dark",
        backgroundColor: "background-selected"
      }
    },

    "selected-dark": {
      include: "material-button",
      style: {
        style: "solid",
        width: 1,
        color: "background-selected-dark",
        backgroundColor: "background-selected-dark"
      }
    },

    "thumbnail": {
      include: "material-button",
      style: {
        style: "solid",
        width: 1,
        color: "box-shadow",
        backgroundColor: "fab-background",
      }
    },

    "thumbnail-selected": {
      include: "thumbnail",
      style: {
        style: "solid",
        width: 1,
        color: "background-selected-dark",
        backgroundColor: "background-selected"
      }
    },

    "progressbar": {
      style: {
        style: "solid",
        width: 0,
        color: "transparent",
        backgroundColor: "progressbar-runner",
      }
    },

    /*
    ---------------------------------------------------------------------------
      Tooltip
    ---------------------------------------------------------------------------
    */
    "tooltip": {
      style: {
        style: "solid",
        width: 1,
        color: "info",
        backgroundColor: "tooltip",
      }
    },

    /*
    ---------------------------------------------------------------------------
      Appmotion
    ---------------------------------------------------------------------------
    */
    "appmotion-buy-credits-input": {
      style: {
        radius: 4
      }
    }
  }
});
