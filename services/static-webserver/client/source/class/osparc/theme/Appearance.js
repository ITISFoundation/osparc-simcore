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
    "material-button-invalid": {},
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
          backgroundColor: "pb-study",
          opacity: 1
        };
        if (states.hovered) {
          style.opacity = 0.5;
        }
        if (states.selected || states.checked) {
          style.opacity = 1;
          style.backgroundColor = "success";
        }
        return style;
      }
    },

    "pb-new":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-new"
        };
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "default-button-active-background";
        }
        if (states.locked || states.disabled) {
          style.cursor = "not-allowed";
          style.backgroundColor = "pb-locked";
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
        if (states.focused || states.selected || states.checked) {
          style.backgroundColor = "success";
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
        return style;
      }
    },

    "pb-dynamic":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-dynamic"
        };
        return style;
      }
    },

    "pb-computational":  {
      include: "pb-listitem",
      style: function(states) {
        const style = {
          backgroundColor: "pb-computational"
        };
        return style;
      }
    },

    "widget/selected-file-layout/download-button/icon": {},
    "widget/selected-file-layout/delete-button/icon": {},
    "pb-dynamic/menu-button/icon": {},
    "pb-template/menu-button/icon": {},
    "pb-study/menu-button/icon": {},
    "pb-computational/menu-button/icon": {
      alias: "image"
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

    "none": {},

    "floating-menu": {
      style: function() {
        return {
          backgroundColor: "background-main",
          padding: 4,
          decorator: "border-simple"
        }
      }
    },

    /*
    ---------------------------------------------------------------------------
      WINDOW-SMALL-CAP CHOOSER
    ---------------------------------------------------------------------------
    */
    "node-ui-cap": {
      include: "window", // get all the settings from window
      alias: "window", // redirect kids to window/kid
      style: function(states) {
        return {
          backgroundColor: states.selected ? "node-selected-background" : "node-background",
          textColor: states.selected ? "text-selected" : "text",
          decorator: states.maximized ? "node-ui-cap-maximized" : "node-ui-cap"
        };
      }
    },

    "node-ui-cap/captionbar": {
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

    "node-ui-cap/title": {
      include: "window/title",
      style: function(states) {
        return {
          marginLeft: 2,
          font: "text-12",
          textColor: states.selected ? "text-selected" : "text"// Dark theme text color
        };
      }
    },

    "node-ui-cap/minimize-button": {
      alias: "window/minimize-button",
      include: "window/minimize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-minimize"]+"/14"
        };
      }
    },

    "node-ui-cap/restore-button": {
      alias: "window/restore-button",
      include: "window/restore-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-restore"]+"/14"
        };
      }
    },

    "node-ui-cap/maximize-button": {
      alias: "window/maximize-button",
      include: "window/maximize-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-maximize"]+"/14"
        };
      }
    },

    "node-ui-cap/close-button": {
      alias: "window/close-button",
      include: "window/close-button",
      style: function(states) {
        return {
          icon: osparc.theme.common.Image.URLS["window-close"]+"/14"
        };
      }
    },

    "node-ui-cap/progress": "progressbar",

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

    /*
    ---------------------------------------------------------------------------
      PROGRESSBAR
    ---------------------------------------------------------------------------
    */

    "progressbar": {
      style: function(states) {
        return {
          decorator: "progressbar",
          padding: 1,
          backgroundColor: "progressbar-runner",
          margin: [7, 10],
          width: 200,
          height: 20
        };
      }
    },

    "progressbar/progress": {
      style: function(states) {
        return {
          backgroundColor: states.disabled ? "progressbar-disabled" : "progressbar"
        };
      }
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

    "splitpane/collapsible-view-left/collapse-button": {},
    "splitpane/collapsible-view-right/collapse-button": {},

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
        if (states.disabled) {
          style.decorator = "form-input-disabled";
          style.backgroundColor = "default-button-disabled-background";
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
          decorator += "-disabled";
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
    "widget/reset-button": {},

    "form-button": {
      style: function(states) {
        const style = {
          decorator: "form-button",
          cursor: "pointer",
          textColor: "default-button-text",
          padding: 5,
          backgroundColor: "default-button"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
          style.textColor = "default-button-text-action";
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
          style.backgroundColor = "default-button-disabled-background";
        }
        if (states.checked || states.selected) {
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
          cursor: "pointer",
          padding: 5,
          textColor: "default-button-text-outline",
          backgroundColor: "default-button-background"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
          style.textColor = "default-button-text-action";
          style.backgroundColor = "default-button-hover-background";
        }
        if (states.focused || states.active) {
          style.decorator = "form-button-focused";
          style.backgroundColor = "default-button-focus-background";
        }
        if (states.disabled) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-disabled";
          style.textColor = "default-button-disabled";
          style.backgroundColor = "default-button-disabled-background";
        }
        if (states.checked || states.selected) {
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
          padding: 5,
          textColor: "fab_text",
          backgroundColor: "fab-background",
          center: true
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
          style.decorator = "form-button-checked";
        }
        return style;
      }
    },

    "thumbnail": {
      include: "form-button",
      style: function(states) {
        const style = {
          decorator: "thumbnail",
          cursor: "pointer",
          padding: 5,
          textColor: "fab_text",
          backgroundColor: "fab-background",
          center: true
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
          style.decorator = "form-button-checked";
        }
        return style;
      }
    },

    "form-button-text": {
      style: function(states) {
        const style = {
          decorator: "form-button-text",
          center: true,
          cursor: "pointer",
          textColor: "link",
          padding: 5,
          alignY: "middle",
          alignX: "center",
          backgroundColor: "transparent"
        };
        if (states.hovered) {
          style.textColor = "contrasted-text-dark";
        }
        if (states.focused) {
          style.textColor = "default-button-focus";
        }
        if (states.disabled) {
          style.cursor = "not-allowed";
          style.textColor = "default-button-disabled";
        }
        return style;
      }
    },

    "menu-button": {
      alias: "atom",

      style: function(states) {
        return {
          cursor: states.disabled ? "not-allowed" : "pointer",
          backgroundColor: states.selected ? "background-selected-dark" : undefined,
          textColor: states.selected ? "default-button-text" : "text",
          padding: [2, 6]
        };
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
        let textColor = "default-button-text-outline";
        let decorator = "form-button-outlined";
        let backgroundColor = "default-button-background";
        let cursor = "pointer";
        let margin = [7, 0, 7, 10];
        if (states.left || states.middle || states.right) {
          margin = [7, 0, 7, 3];
        }
        if (states.hovered) {
          textColor = "default-button-text-action";
          decorator = "form-button-hovered";
          backgroundColor = "default-button-hover-background";
        }
        if (states.pressed) {
          textColor = "default-button-text-action";
          decorator = "form-button-active";
          backgroundColor = "default-button-active-background";
        }
        if (states.focused) {
          textColor = "default-button-focus";
          decorator = "form-button-focused";
          backgroundColor = "default-button-focus-background";
        }
        if (states.selected || states.checked) {
          textColor = "default-button-disabled";
          cursor = "default";
          decorator = "form-button-checked";
          backgroundColor = "default-button-disabled-background";
        }

        decorator;

        return {
          textColor: textColor,
          cursor: cursor,
          decorator: decorator,
          margin: margin,
          padding: 5,
          backgroundColor: backgroundColor
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
        var decorator = "form-button-outlined";
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
        let decorator = "form-button-outlined";
        if (states.hovered || states.pressed || states.focused) {
          decorator += "-hovered";
        }

        if (states.checked || states.selected) {
          decorator += "-checked";
        }

        decorator += "-right";

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
      include: "form-button"
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
      TabButtons
    ---------------------------------------------------------------------------
    */

    "tab-button": {
      include: "form-button",
      style: function(states) {
        const style = {
          decorator: "tab-button",
          cursor: "pointer",
          padding: 5,
          textColor: "default-button-text",
          backgroundColor: "default-button-background"
        };
        if (states.hovered) {
          style.decorator = "form-button-hovered";
        }
        if (states.focused) {
          style.decorator = "form-button-focused";
        }
        if (states.active) {
          style.decorator = "tab-button-selected";
        }
        if (states.disabled) {
          style.cursor = "not-allowed";
          style.decorator = "form-button-disabled";
          style.textColor = "default-button-disabled";
        }
        if (states.checked || states.selected) {
          style.decorator = "tab-button-selected";
        }
        return style;
      }
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
        backgroundColor: "hint-background",
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
    "editlabel-label": {
      include: "label",
      style: state => ({
        decorator: state.hovered && state.editable ? "border-editable" : "rounded",
        marginLeft: state.hovered && state.editable ? 0 : 1,
        padding: 5,
        cursor: state.editable ? "text" : "auto",
        backgroundColor: "input_background"
      })
    },

    "editlabel-input": {
      include: "textfield",
      style: () => ({
        padding: 5,
        minWidth: 120,
        backgroundColor: "transparent"
      })
    },

    /*
    ---------------------------------------------------------------------------
      Tooltip
    ---------------------------------------------------------------------------
    */
    "tooltip": {
      style: state => ({
        decorator: "tooltip",
        padding: [5, 10],
        // showTimeout is themeable so it can be tuned
        // it was defaulted to 700 which was too short
        showTimeout: 2000,
        hideTimeout: 6000,
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

    "chip-button": {
      include: "material-button",
      style: () => ({
        iconPosition: "right",
        textColor: "text",
        alignY: "middle",
        paddingRight: 6,
        paddingLeft: 6,
        maxHeight: 26,
        maxWidth: 260,
        decorator: "chip-button"
      })
    },

    "filter-toggle-button": {
      include: "material-button",
      alias: "material-button",
      style: states => ({
        font: "text-13",
        textColor: "text",
        padding: 6,
        gap: 8,
        decorator: (states.hovered || states.pressed || states.checked) ? "filter-toggle-button-selected" : "filter-toggle-button"
      })
    },

    "filter-toggle-button/label": {
      include: "material-button/label",
      style: () => ({
        textColor: "text"
      })
    },

    "filter-toggle-button/icon": {
      include: "material-button/icon",
      style: () => ({
        width: 25,
        scale: true
      })
    },

    /*
    ---------------------------------------------------------------------------
      virtual overrides
    ---------------------------------------------------------------------------
    */

    "virtual-tree": {
      include: "tree",
      alias: "tree",
      style: function(states) {
        return {
          itemHeight: 30
        };
      }
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
    },

    /*
    ---------------------------------------------------------------------------
      Appmotion
    ---------------------------------------------------------------------------
    */
    "appmotion-button": {
      include: "lg-button",
      alias: "lg-button",
      style: state => {
        const style = {
          padding: [10, 25]
        };
        if (state.disabled) {
          style.backgroundColor = "default-button-disabled-background";
        }
        return style;
      }
    },

    "appmotion-button-action": {
      include: "appmotion-button",
      alias: "appmotion-button",
      style: state => {
        const style = {
          backgroundColor: "strong-main"
        };
        if (state.disabled) {
          style.backgroundColor = "default-button-disabled-background";
        }
        return style;
      }
    },

    "appmotion-button/label": {
      include: "lg-button/label",
      style: state => ({
        font: "title-16"
      })
    },

    "appmotion-buy-credits-input": {
      include: "textfield",
      style: state => ({
        backgroundColor: state.disabled ? "transparent" : "background-main-1",
        padding: [10, 15],
        font: "text-18",
        decorator: "appmotion-buy-credits-input"
      })
    },

    "appmotion-buy-credits-select": {
      include: "selectbox",
      alias: "selectbox",
      style: state => ({
        backgroundColor: state.disabled ? "transparent" : "background-main-1",
        padding: [10, 15],
        font: "text-14",
        decorator: "appmotion-buy-credits-input"
      })
    },

    "appmotion-buy-credits-select/list": {
      include: "selectbox/list",
      alias: "selectbox/list",
      style: state => ({
        backgroundColor: "background-main-1"
      })
    },

    "appmotion-buy-credits-spinner": {
      include: "spinner",
      alias: "spinner"
    },

    "appmotion-buy-credits-spinner/textfield": {
      include: "appmotion-buy-credits-input",
      alias: "appmotion-buy-credits-input",
      style: state => ({
        font: "text-14"
      })
    },

    "appmotion-buy-credits-checkbox": {
      include: "checkbox",
      alias: "checkbox",
      style: state => ({
        icon: state.checked ? "@MaterialIcons/check_box/20" : "@MaterialIcons/check_box_outline_blank/20"
      })
    }
  }
});
