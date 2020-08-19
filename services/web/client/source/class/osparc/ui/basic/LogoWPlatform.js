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
 * Theme dependant oSparc logo with platofrm name
 */
qx.Class.define("osparc.ui.basic.LogoWPlatform", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      alignX: "center"
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

          this._add(logoContainer, {
            height: "100%"
          });
          break;
        }
        case "platform": {
          control = new qx.ui.basic.Label().set({
            font: "text-8"
          });

          osparc.utils.LibVersions.getPlatformName()
            .then(platformName => {
              platformName = platformName.toUpperCase();
              if (osparc.utils.Utils.isInZ43()) {
                platformName = "z43" + platformName;
              }
              control.setValue(platformName);
            });

          this._add(control, {
            bottom: 3,
            right: 0
          });
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
        height: size.height
      });
    },

    setFont: function(font) {
      const platform = this.getChildControl("platform");
      platform.setFont(font);
    }
  }
});
