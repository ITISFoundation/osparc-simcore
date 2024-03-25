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
  extend: osparc.po.BaseView,

  members: {
    _buildLayout: function() {
      const params = {
        url: {
          productName: osparc.product.Utils.getProductName()
        }
      };
      osparc.data.Resources.fetch("productMetadata", "get", params)
        .then(respData => {
          // "templates" has its own section
          delete respData["templates"];
          const invitationRespViewer = new osparc.ui.basic.JsonTreeWidget(respData, "product-metadata");
          const container = new qx.ui.container.Scroll();
          container.add(invitationRespViewer);
          this._add(container, {
            flex: 1
          });
        });
    }
  }
});
