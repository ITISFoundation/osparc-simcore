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

    [
      "osparc/osparc-red.svg",
      "osparc/osparc-white.svg"
    ].forEach(logo => {
      let image = new qx.ui.basic.Image(logo).set({
        width: 92,
        height: 32,
        scale: true
      });
      this._add(image);
    }, this);
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
