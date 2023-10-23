/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * App/Theme dependant logo with platform name
 */
qx.Class.define("osparc.ui.basic.LogoWPlatform", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(-5));

    this.set({
      alignX: "center",
      alignY: "middle",
      padding: 3
    });

    this.getChildControl("logo");
    this.getChildControl("platform");
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "logo": {
          control = new osparc.ui.basic.Logo();

          const logoContainer = new qx.ui.container.Composite(new qx.ui.layout.HBox().set({
            alignY: "middle"
          }));
          logoContainer.add(control);

          this._add(logoContainer);
          break;
        }
        case "platform": {
          control = new qx.ui.basic.Label().set({
            alignX: "right",
            font: "text-9"
          });

          let platformName = osparc.store.StaticInfo.getInstance().getPlatformName();
          platformName = platformName.toUpperCase();
          if (osparc.utils.Utils.isInZ43()) {
            platformName = "Z43 " + platformName;
          }
          control.setValue(platformName);
          control.bind("value", this, "paddingTop", {
            converter: value => value ? 3 : 7
          });
          this._add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    setSize: function(size) {
      this.set({
        maxWidth: size.width,
        maxHeight: size.height
      });
      this.getChildControl("logo").set({
        width: size.width,
        height: parseInt(size.height*0.8)
      });
    },

    setFont: function(font) {
      const platform = this.getChildControl("platform");
      platform.setFont(font);
    }
  }
});
