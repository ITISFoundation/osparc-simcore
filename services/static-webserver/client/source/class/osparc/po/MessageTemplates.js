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

qx.Class.define("osparc.po.MessageTemplates", {
  extend: osparc.po.BaseView,

  members: {
    __messageTemplates: null,

    _buildLayout: function() {
      const params = {
        url: {
          productName: osparc.product.Utils.getProductName()
        }
      };
      osparc.data.Resources.fetch("productMetadata", "get", params)
        .then(respData => {
          this.__messageTemplates = respData["templates"];
          this.__buildLayout();
        });
    },

    __buildLayout: function() {
      this._removeAll();

      const templatesSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      this._add(templatesSB);

      const htmlViewer = this.__htmlViewer = new osparc.editor.HtmlEditor().set({
        minHeight: 400
      });
      htmlViewer.getChildControl("cancel-button").exclude();
      const container = new qx.ui.container.Scroll();
      container.add(htmlViewer, {
        flex: 1
      });
      this._add(container, {
        flex: 1
      });

      templatesSB.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const templateId = selection[0].getModel();
          this.__populateMessage(templateId);
        }
      }, this);
      this.__messageTemplates.forEach(template => {
        const lItem = new qx.ui.form.ListItem(template.id, null, template.id);
        templatesSB.add(lItem);
      });
      htmlViewer.addListener("textChanged", e => {
        const newTemplate = e.getData();
        const templateId = templatesSB.getSelection()[0].getModel();
        this.__saveTemplate(templateId, newTemplate);
      });
    },

    __populateMessage: function(templateId) {
      const found = this.__messageTemplates.find(template => template.id === templateId);
      if (found) {
        this.__htmlViewer.setText(found.content);
      }
    },

    __saveTemplate: function(templateId, newTemplate) {
      const productName = osparc.product.Utils.getProductName();
      const params = {
        url: {
          productName,
          templateId
        },
        data: {
          content: newTemplate
        }
      };
      osparc.data.Resources.fetch("productMetadata", "updateEmailTemplate", params)
        .then(() => osparc.FlashMessenger.logAs(this.tr("Template updated"), "INFO"))
        .catch(err => {
          console.error(err);
          osparc.FlashMessenger.logAs(err, "ERROR");
        })
        .finally(() => this._buildLayout());
    }
  }
});
