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

qx.Class.define("osparc.po.ProductInfo", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__fetchInfo();
  },

  members: {
    __fetchInfo: function() {
      const params = {
        url: {
          productName: osparc.product.Utils.getProductName()
        }
      };
      osparc.data.Resources.fetch("productMetadata", "get", params)
        .then(respData => {
          const invitationRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "product-metadata");
          const container = new qx.ui.container.Scroll().set({
            maxHeight: 500
          });
          container.add(invitationRespViewer);
          this._add(container, {
            flex: 1
          });
        });
    }
  }
});
