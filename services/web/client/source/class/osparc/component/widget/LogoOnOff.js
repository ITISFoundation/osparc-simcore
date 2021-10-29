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
 *   let logo = osparc.component.widget.LogoOnOff.getInstance();
     logo.online(true/false);
 * </pre>
 */

qx.Class.define("osparc.component.widget.LogoOnOff", {
  extend: qx.ui.container.Stack,

  type: "singleton",

  construct: function() {
    this.base(arguments);

    const offLogoContainer = new qx.ui.container.Composite(new qx.ui.layout.VBox().set({
      alignX: "center"
    }));
    offLogoContainer.add(new qx.ui.core.Spacer(null, 8));
    const offLogo = new qx.ui.basic.Image("osparc/offline.svg").set({
      width: 92,
      height: 35,
      scale: true
    });
    offLogoContainer.add(offLogo, {
      flex: 1
    });
    this.add(offLogoContainer);

    const onLogo = new osparc.ui.basic.LogoWPlatform();
    onLogo.setSize({
      width: 92,
      height: 50
    });
    onLogo.setFont("text-9");
    this.add(onLogo);
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
    _applyOnline: function(value) {
      this.setSelection([this.getSelectables()[value ? 1 : 0]]);
    }
  }
});
