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

    const width = 92;
    const height = 32;

    const offLogo = new qx.ui.basic.Image("osparc/osparc-red.svg").set({
      width,
      height,
      scale: true
    });
    this.add(offLogo);

    const onLogo = new osparc.ui.basic.OSparcLogo().set({
      width,
      height
    });
    this.add(onLogo);
  },

  properties: {
    onLine: {
      check: "Boolean",
      init: false,
      nullable: false,
      apply: "_applyOnLine"
    }
  },

  members: {
    _applyOnLine: function(value) {
      this.setSelection([this.getSelectables()[value ? 1 : 0]]);
    }
  }
});
