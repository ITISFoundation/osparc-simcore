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
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__fetchInfo();
  },

  members: {
    __messageTemplates: null,

    __fetchInfo: function() {
      const params = {
        url: {
          productName: osparc.product.Utils.getProductName()
        }
      };
      osparc.data.Resources.fetch("productMetadata", "get", params)
        .then(respData => {
          // dummy
          respData["messageTemplates"] = [{
            templateId: "t1",
            template: "<b>Hello world</b>"
          }, {
            templateId: "t2",
            template: "Welcome to Sim4Life\
            <p>\
              Dear {{ name }} <br><br>\
              Thank you for your interest in Sim4Life. You have successfully registered for {{ host }}.<br>\
              Please activate your account via the link below:\
            </p>\
            <p>\
              <a href='{{ link }}'>{{ link }}</a>\
            </p>\
            <p>\
              Please don't hesitate to contact us at {{ support_email }} if you need further help.<br><br>\
              Best regards <br>\
              The <i>Sim4Life</i> Team\
            </p>\
            "
          }];
          this.__messageTemplates = respData["messageTemplates"];
          this.__buildLayout();
        });
    },

    __buildLayout: function() {
      const templatesSB = new qx.ui.form.SelectBox().set({
        allowGrowX: false
      });
      this._add(templatesSB);

      const htmlViewer = this.__htmlViewer = new osparc.editor.HtmlEditor().set({
        minHeight: 400
      });
      const container = new qx.ui.container.Scroll();
      container.add(htmlViewer, {
        flex: 1
      });
      this._add(container, {
        flex: 1
      });

      templatesSB.addListener("changeSelection", e => {
        const templateId = e.getData()[0].getModel();
        this.__populateMessage(templateId);
      }, this);
      this.__messageTemplates.forEach(template => {
        const lItem = new qx.ui.form.ListItem(template.templateId, null, template.templateId);
        templatesSB.add(lItem);
      });
    },

    __populateMessage: function(templateId) {
      const found = this.__messageTemplates.find(template => template.templateId === templateId);
      if (found) {
        this.__htmlViewer.setText(found.template);
      }
    }
  }
});
