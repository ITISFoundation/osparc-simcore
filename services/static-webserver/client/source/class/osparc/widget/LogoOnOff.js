/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton that contains a stack of two logos.
 *
 * If online the white logo will be selected, if the webserver gets disconnected, the logo will turn red
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let logo = osparc.widget.LogoOnOff.getInstance();
     logo.online(true/false);
 * </pre>
 */

qx.Class.define("osparc.widget.LogoOnOff", {
  extend: qx.ui.container.Stack,

  type: "singleton",

  construct: function() {
    this.base(arguments);

    this.getChildControl("off-logo");
    this.getChildControl("on-logo");
  },

  properties: {
    online: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyOnline"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "off-logo-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
            alignX: "center"
          }));
          control.add(new qx.ui.core.Spacer(null, 8));
          this.add(control);
          break;
        }
        case "off-logo": {
          control = new qx.ui.basic.Image("osparc/offline.svg").set({
            width: 92,
            height: 35,
            scale: true
          });
          const container = this.getChildControl("off-logo-container");
          container.add(control, {
            flex: 1
          });
          break;
        }
        case "on-logo": {
          control = new osparc.ui.basic.LogoWPlatform();
          control.setSize({
            width: 100,
            height: 50
          });
          control.setFont("text-9");
          this.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _applyOnline: function(value) {
      this.setSelection([this.getSelectables()[value ? 1 : 0]]);
    }
  }
});
