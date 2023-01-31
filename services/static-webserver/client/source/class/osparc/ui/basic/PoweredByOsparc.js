/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * App/Theme dependant osparc logo with powerwed by text
 */
qx.Class.define("osparc.ui.basic.PoweredByOsparc", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(2));

    this.set({
      toolTipText: this.tr("powered by oSPARC"),
      alignX: "center",
      alignY: "middle",
      cursor: "pointer",
      padding: 3
    });

    this.addListener("tap", () => this.__popUpAboutOsparc());

    this.getChildControl("powered-by");
    this.getChildControl("logo");

    this.__resetSourcePath();

    const themeManager = qx.theme.manager.Meta.getInstance();
    themeManager.addListener("changeTheme", () => this.__resetSourcePath(), this);
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "powered-by": {
          control = new qx.ui.basic.Label(this.tr("powered by")).set({
            alignX: "center",
            font: "text-9"
          });
          this._add(control);
          break;
        }
        case "logo": {
          control = new qx.ui.basic.Image().set({
            width: 47,
            height: 38,
            scale: true,
            alignX: "center"
          });
          const logoContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "bottom"
          }));
          logoContainer.add(control);
          this._add(logoContainer);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __resetSourcePath: function() {
      const colorManager = qx.theme.manager.Color.getInstance();
      const textColor = colorManager.resolve("text");
      const lightLogo = osparc.utils.Utils.getColorLuminance(textColor) > 0.4;
      this.getChildControl("logo").set({
        source: lightLogo ? "osparc/osparc-o-white.svg" : "osparc/osparc-o-black.svg"
      });
    },

    __popUpAboutOsparc: function() {
      console.log("hey there");
    }
  }
});
