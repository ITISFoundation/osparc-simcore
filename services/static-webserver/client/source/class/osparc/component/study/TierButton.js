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

qx.Class.define("osparc.component.study.TierButton", {
  extend: qx.ui.form.ToggleButton,

  construct: function(tierInfo) {
    this.base(arguments);

    this.set({
      padding: 10,
      minWidth: 120,
      maxWidth: 120,
      center: true
    });
    this.getContentElement().setStyles({
      "border-radius": "4px"
    });

    this.__tierInfo = tierInfo;

    this.__buildLayout();
  },

  properties: {
    simplified: {
      check: "Boolean",
      init: null,
      nullable: true,
      event: "changeSimplified",
      apply: "__buildLayout"
    }
  },

  members: {
    __tierInfo: null,

    __buildLayout: function() {
      const tierInfo = this.__tierInfo;

      const toFixedIfNecessary = (value, dp) => Number(parseFloat(value).toFixed(dp));

      if (this.isSimplified()) {
        this._setLayout(new qx.ui.layout.HBox(5));
        this._add(new qx.ui.basic.Label().set({
          value: tierInfo.title + ": " + tierInfo.price,
          font: "text-16"
        }));
      } else {
        this._setLayout(new qx.ui.layout.VBox(5));

        this._add(new qx.ui.basic.Label().set({
          value: tierInfo.title,
          font: "text-16"
        }));
        if (!this.isSimplified()) {
          Object.keys(tierInfo.resources).forEach(resourceKey => {
            this._add(new qx.ui.basic.Label().set({
              value: resourceKey + ": " + toFixedIfNecessary(tierInfo.resources[resourceKey]),
              font: "text-12"
            }));
          });
        }
        this._add(new qx.ui.basic.Label().set({
          value: qx.locale.Manager.tr("Credits/h") + ": " + tierInfo.price,
          font: "text-14"
        }));
      }
    },

    getTierInfo: function() {
      return this.__tierInfo;
    }
  }
});
