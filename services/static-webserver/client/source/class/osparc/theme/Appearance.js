/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Tobias Oetiker (oetiker)

************************************************************************ */

qx.Theme.define("osparc.theme.Appearance", {
  extend: osparc.theme.common.Appearance,

  appearances: {
    "pb-list": {
      include: "list",
      alias:   "list",
      style: function(states) {
        return {
          decorator: null,
          padding: 0
        };
      }
    },

    "pb-listitem":  {
      alias: "material-button",
      include: "material-button",
      style: function(states) {
        const style = {
          decorator: "pb-listitem",
          padding: 5,
          backgroundColor: "background-card-overlay"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-new":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "success_bg"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-study":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-study"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-template":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-template"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-dynamic":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-dynamic"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-computational":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-computational"
        };
        if (states.hovered) {
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        return style;
      }
    },

    "pb-study/lock-status":  {
      style: function() {
        return {
          decorator: "pb-locked",
          cursor: "disabled"
        };
      }
    },

    "pb-template/lock-status":  {
      style: function() {
        return {
          decorator: "pb-locked",
          cursor: "disabled"
        };
      }
    },

    "pb-computational/lock-status":  {
      style: function() {
        return {
          decorator: "pb-locked",
          cursor: "disabled"
        };
      }
    },

    "pb-dynamic/lock-status":  {
      style: function() {
        return {
          decorator: "pb-locked",
          cursor: "disabled"
        };
      }
    },

    "selectable": {
      include: "material-button",
      style: function(states) {
        const style = {
          decorator: "no-radius-button",
          padding: 5,
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.backgroundColor = "background-main-2";
        }
        if (states.selected || states.checked) {
          style.backgroundColor = "background-selected";
        }
        return style;
      }
    },

    /*
    ---------------------------------------------------------------------------
      WINDOW-SMALL-CAP CHOOSER
    ---------------------------------------------------------------------------
    */
    "window-small-cap": {
      include: "window", // get all the settings from window
      alias: "window", // redirect kids to window/kid
      style: function(states) {
        return {
          backgroundColor: states.selected ? "node-selected-background" : "node-background",
          decorator: states.maximized ? "window-small-cap-maximized" : "window-small-cap"
        };
      }
    },

    "window-small-cap/captionbar": {
      include: "window/captionbar", // load defaults from window captionbar
      alias: "window/captionbar", // redirect kids
      style: function(states) {
        return {
          padding: [0, 3, 0, 3],
          minHeight: 20,
          backgroundColor: "transparent",
          decorator: "workbench-small-cap-captionbar"
        };
      }
    },

    "window-small-cap/title": {
      include: "window/title",
      style: function(states) {
        return {
          marginLeft: 2,
          font: "text-12",
          textColor: "rgba(20, 20, 20, 1)" // Dark theme text color
        };
      }
    },

    "window-small-cap/minimize-button": {
      alias: "window/minimize-button",
      include: "window/minimize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-minimize"]+"/14"
        };
      }
    },

    "window-small-cap/restore-button": {
      alias: "window/restore-button",
      include: "window/restore-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-restore"]+"/14"
        };
      }
    },

    "window-small-cap/maximize-button": {
      alias: "window/maximize-button",
      include: "window/maximize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-maximize"]+"/14"
        };
      }
    },

    "window-small-cap/close-button": {
      alias: "window/close-button",
      include: "window/close-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-close"]+"/14"
        };
      }
    },

    "window-small-cap/progress": "progressbar",

    "service-window": {
      include: "window",
      alias: "window",
      style: state => ({
        decorator: state.maximized ? "service-window-maximized" : "service-window"
      })
    },
    "service-window/captionbar": {
      include: "window/captionbar",
      style: state => ({
        backgroundColor: "transparent",
        decorator: "workbench-small-cap-captionbar"
      })
    },
    "info-service-window": {
      include: "service-window",
      alias: "service-window",
      style: state => ({
        maxHeight: state.maximized ? null : 500
      })
    },

    "dialog-window-content": {
      style: () => ({
        backgroundColor: "transparent_overlay"
      })
    },
    /*
    ---------------------------------------------------------------------------
      PanelView
    ---------------------------------------------------------------------------
    */
    "panelview": {
      style: state => ({
        decorator: "panelview"
      })
    },
    "panelview/title": {
      style: state => ({
        font: "title-14",
        cursor: "pointer"
      })
    },
    "panelview/caret": {
      style: state => ({
        cursor: "pointer"
      })
    },
    "panelview-titlebar": {
      style: state => ({
        height: 24,
        padding: [0, 5],
        alignY: "middle"
      })
    },
    "panelview-content": {
      style: state => ({
        decorator: "panelview-content",
        margin: [0, 4, 4, 4]
      })
    },

    /*
    ---------------------------------------------------------------------------
      Toolbar
    ---------------------------------------------------------------------------
    */
    "toolbar-textfield": {
      include: "form-input",
      style: state => ({
        backgroundColor: "transparent",
        marginTop: 8
      })
    },
    "toolbar-label": {
      style: state => ({
        marginTop: 11,
        marginRight: 3
      })
    },
    "textfilter": {},
    "textfilter/textfield": "toolbar-textfield",

    "autocompletefilter": {},
    "autocompletefilter/autocompletefield/textfield": {
      include: "toolbar-textfield",
      style: state => ({
        paddingRight: 15
      })
    },
    "autocompletefilter/autocompletefield/button": {},

    "toolbar-selectbox": {
      include: "textfield",
      alias: "selectbox",
      style: () => ({
        margin: [7, 10],
        paddingLeft: 5
      })
    },
    "toolbar-selectbox/arrow": {
      include: "selectbox/arrow",
      style: style => ({
        cursor: style.disabled ? "auto" : "pointer"
      })
    },
    "toolbar-selectbox/list": {
      include: "selectbox/list",
      style: () => ({
        padding: 0
      })
    },

    "toolbar-progressbar": {
      include: "progressbar",
      alias: "progressbar",
      style: () => ({
        margin: [7, 10]
      })
    },

    /*
    ---------------------------------------------------------------------------
      Splitpane
    ---------------------------------------------------------------------------
    */
    "splitpane/splitter": {
      style: state => ({
        visible: false
      })
    },

    /*
    ---------------------------------------------------------------------------
      NodePorts
    ---------------------------------------------------------------------------
    */
    "node-ports": {
      style: state => ({
        backgroundColor: "background-main-2"
      })
    },

    /*
    ---------------------------------------------------------------------------
      ServiceBrowser
    ---------------------------------------------------------------------------
    */
    "service-browser": {
      style: state => ({
        padding: 8,
        decorator: "service-browser"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Input Fields
    ---------------------------------------------------------------------------
    */

    "form-input": {
      style: function(states) {
        const style = {
          decorator: "form-input",
          padding: 5,
          backgroundColor: "input_background"
        };
        if (states.hovered) {
          style.backgroundColor = "info";
        }
        if (states.focused) {
          style.decorator = "form-input-focused";
        }
        return style;
      }
    },

    "form-password": {
      include: "form-input",
      style: function(states) {
        const style = {
          decorator: "form-input",
          padding: 5,
          backgroundColor: "input_background"
        };
        if (states.focused) {
          style.decorator = "form-input-focused";
        }
        return style;
      }
    },

    "material-textfield": {
      style: function(states) {
        var textColor;

        if (states.disabled) {
          textColor = "text-disabled";
        } else if (states.showingPlaceholder) {
          textColor = "text-placeholder";
        } else {
          textColor = undefined;
        }

        var decorator;
        var padding;
        decorator = "form-input";
        padding = [3, 5, 4, 5];
        if (states.readonly) {
          decorator += "-readonly";
          padding = [3, 5, 5, 5];
        } else if (states.disabled) {
          decorator += "-disabled";
        } else if (states.focused) {
          decorator += "-focused";
          if (states.invalid) {
            decorator += "-invalid";
          }
          padding = [3, 5, 4, 5];
        } else if (states.invalid) {
          decorator += "-invalid";
        }

        return {
          decorator: decorator,
          padding: padding,
          textColor: textColor,
          backgroundColor: states.disabled ? "input_background_disable" : "input_background"
        };
      }
    },

    /*
    ---------------------------------------------------------------------------
      Buttons
    ---------------------------------------------------------------------------
    */

    "form-button": {
      style: function(states) {
        const style = {
          decorator: "form-button",
          cursor: "pointer",
          textColor: "default-button-text",
          padding: 5,
          alignY: "middle",
          alignX: "center",
          backgroundColor: "default-button"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.focused) {
          style.decorator = "form-button-focused";
          style.backgroundColor = "default-button-focus-background";
        }
        if (states.disabled) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-disabled";
          style.textColor = "default-button-disabled";
          style.backgroundColor = "transparent";
        }
        if (states.checked || states.selected) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-checked";
        }
        return style;
      }
    },
    "form-button-outlined": {
      include: "form-button",
      style: function(states) {
        const style = {
          decorator: "form-button-outlined",
          padding: 5,
          textColor: "default-button-text-outline",
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
        }
        if (states.focused) {
          style.decorator = "form-button-focused";
        }
        if (states.active) {
          style.decorator = "form-button-focused";
        }
        if (states.disabled) {
          style.decorator = "form-button-disabled";
          style.textColor = "default-button-disabled";
        }
        if (states.checked || states.selected) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-checked";
        }
        return style;
      }
    },

    "fab-button": {
      include: "form-button",
      style: function(states) {
        const style = {
          decorator: "fab-button",
          cursor: "pointer",
          padding: [8, 16],
          textColor: "fab_text",
          backgroundColor: "background-card-overlay"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
        }
        if (states.focused) {
          style.decorator = "form-button-focused";
        }
        if (states.active) {
          style.decorator = "form-button-active";
        }
        if (states.disabled) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-disabled";
        }
        if (states.checked || states.selected) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-checked";
        }
        return style;
      }
    },

    "text-button": {
      include: "form-button",
      style: function(states) {
        const style = {
          decorator: "text-button",
          textColor: "default-button",
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.textColor = "default-button-hover";
        }
        if (states.focused) {
          style.textColor = "default-button-focus";
        }
        if (states.active) {
          style.textColor = "default-button-active";
        }
        if (states.disabled) {
          style.textColor = "default-button-disabled";
        }
        return style;
      }
    },

    "link-button": {
      include: "material-button",
      style: state => ({
        backgroundColor: "transparent",
        textColor: state.hovered ? "text" : "text-darker"
      })
    },

    "xl-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "xl-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "lg-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "lg-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    "md-button": {
      include: "material-button",
      alias: "material-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 25,
        center: true
      })
    },

    "md-button/label": {
      include: "material-button/label",
      style: state => ({
        font: "text-14"
      })
    },

    "toolbar-button": {
      alias: "atom",
      style: function(states) {
        // set the margin
        let textColor = "default-button-text";
        let decorator = "form-button";
        let cursor = "pointer";
        let margin = [7, 0, 7, 10];
        if (states.left || states.middle || states.right) {
          margin = [7, 0, 7, 3];
        }
        if (states.hovered) {
          textColor = "default-button-text-action";
          decorator = "form-button-hovered";
        }
        if (states.pressed) {
          textColor = "default-button-text-action";
          decorator = "form-button-active";
        }
        if (states.focused) {
          textColor = "default-button-focus";
          decorator = "form-button-focused";
        }
        if (states.selected || states.checked) {
          textColor = "default-button-disabled";
          cursor = "default";
          decorator = "form-button-checked";
        }

        decorator;

        return {
          textColor: textColor,
          cursor: cursor,
          decorator: decorator,
          margin: margin,
          padding: 5
        };
      }
    },

    "toolbar-splitbutton/button": {
      alias: "toolbar-button",
      include: "toolbar-button",
      style: function(states) {
        // set the margin
        var margin = [7, 0, 7, 10];
        if (states.left || states.middle || states.right) {
          margin = [7, 0, 7, 3];
        }
        var decorator = "form-button";
        if (states.hovered || states.pressed || states.focused || states.checked) {
          decorator += "-hovered";
        }
        decorator += "-left";

        return {
          decorator: decorator,
          margin: margin
        };
      }
    },

    "toolbar-splitbutton/arrow": {
      alias: "image",
      include: "toolbar-button",
      style: function(states) {
        // set the margin
        var margin = [7, 10, 7, 0];
        if (states.left || states.middle || states.right) {
          margin = [7, 3, 7, 0];
        }
        let decorator = "form-button-right";
        if (states.hovered || states.pressed || states.focused) {
          decorator = "form-button-hovered-right";
        }

        if (states.checked || states.selected) {
          decorator = "form-button-checked-right";
        }

        return {
          icon: osparc.theme.common.Image.URLS["arrow-down"],
          decorator: decorator,
          margin: margin
        };
      }
    },

    "toolbar-xl-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 50,
        center: true
      })
    },

    "toolbar-xl-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "toolbar-lg-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 35,
        center: true
      })
    },

    "toolbar-lg-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-16"
      })
    },

    "toolbar-md-button": {
      include: "toolbar-button",
      alias: "toolbar-button",
      style: state => ({
        allowStretchY: false,
        allowStretchX: false,
        minHeight: 25,
        center: true
      })
    },

    "toolbar-md-button/label": {
      include: "toolbar-button/label",
      style: state => ({
        font: "text-14"
      })
    },

    "no-shadow-button": {
      alias: "atom",
      style: function(states) {
        var decorator = "toolbar-button";
        if (states.hovered || states.pressed || states.checked) {
          decorator += "-hovered";
        }
        return {
          cursor: states.disabled ? undefined : "pointer",
          decorator: decorator,
          textColor: "material-button-text",
          padding: [3, 5]
        };
      }
    },

    // override in product
    "strong-button": {
      include: "material-button",
      style: state => ({
        decorator: state.hovered || state.focused ? "strong-bordered-button" : "no-border",
        backgroundColor: "strong-main",
        textColor: "rgba(216, 216, 216, 1)" // dark theme's text color
      })
    },

    "danger-button": {
      include: "form-button",
      style: state => ({
        decorator: state.hovered || state.focused ? "form-button-danger-hover" : "form-button-danger",
        backgroundColor: state.hovered || state.focused ? "default-button-hover-background" : "error",
        textColor: state.hovered || state.focused ? "default-button-text" : "default-button-text" // dark theme's text color
      })
    },

    /*
    ---------------------------------------------------------------------------
      FlashMessage
    ---------------------------------------------------------------------------
    */
    "flash": {
      style: () => ({
        padding: 12,
        backgroundColor: "background-main-3",
        decorator: "flash"
      })
    },
    "flash/badge": {
      style: () => ({
        decorator: "flash-badge"
      })
    },

    /*
    ---------------------------------------------------------------------------
      GroupBox
    ---------------------------------------------------------------------------
    */
    "settings-groupbox": "groupbox",
    "settings-groupbox/frame": {
      include: "groupbox/frame",
      style: state => ({
        decorator: "no-border"
      })
    },
    "settings-groupbox/legend": {
      include: "groupbox/legend",
      style: state => ({
        font: "title-16"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Hints
    ---------------------------------------------------------------------------
    */
    "hint": {
      style: state => ({
        backgroundColor: "background-main-2",
        decorator: "hint",
        padding: 5
      })
    },

    /*
    ---------------------------------------------------------------------------
      Chip
    ---------------------------------------------------------------------------
    */
    "chip": {
      include: "atom",
      alias: "atom",
      style: state => ({
        decorator: "chip",
        backgroundColor: "background-main-1",
        padding: [3, 5]
      })
    },

    "chip/label": {
      include: "atom/label",
      style: state => ({
        font: "text-10"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Dashboard
    ---------------------------------------------------------------------------
    */
    "dashboard": {
      include: "tabview",
      alias: "tabview"
    },

    "dashboard/pane": {
      style: state => ({
        padding: [0, 0, 0, 15]
      })
    },

    "dashboard/bar/content": {
      style: state => ({
        width: 120,
        paddingTop: 15
      })
    },

    "dashboard-page": {
      include: "tabview-page",
      alias: "tabview-page"
    },

    "dashboard-page/button": {
      include: "tabview-page/button",
      alias: "tabview-page/button",
      style: state => ({
        font: state.checked ? "title-16" : "text-16"
      })
    },

    /*
    ---------------------------------------------------------------------------
      EditLabel
    ---------------------------------------------------------------------------
    */
    "editlabel": {},
    "editlabel/label": {
      include: "atom/label",
      style: state => ({
        decorator: state.hovered && state.editable ? "border-editable" : null,
        marginLeft: state.hovered && state.editable ? 0 : 1,
        padding: [2, state.hovered && state.editable ? 2 : 3, 2, 2],
        cursor: state.editable ? "text" : "auto"
      })
    },
    "editlabel/input": {
      include: "textfield",
      style: state => ({
        paddingTop: 4,
        paddingLeft: 3,
        minWidth: 80,
        backgroundColor: "transparent"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Tag
    ---------------------------------------------------------------------------
    */
    "tag": {
      include: "atom/label",
      style: state => ({
        decorator: "tag",
        padding: [1, 5]
      })
    },
    "tagitem": {
      style: () => ({
        decorator: "tagitem",
        padding: 5
      })
    },
    "tagitem/colorbutton": {
      include: "material-button",
      alias: "material-button",
      style: () => ({
        decorator: "tagitem-colorbutton"
      })
    },
    "tagbutton": {
      include: "material-button",
      alias: "material-button",
      style: () => ({
        decorator: "tagbutton"
      })
    },

    "margined-layout": {
      style: () => ({
        margin: [7, 10]
      })
    },

    /*
    ---------------------------------------------------------------------------
      jsonforms
    ---------------------------------------------------------------------------
    */
    "form-array-container": {
      style: () => ({
        padding: 10,
        decorator: "border-editable"
      })
    }
  }
});
