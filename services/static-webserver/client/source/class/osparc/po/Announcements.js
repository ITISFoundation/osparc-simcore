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

qx.Class.define("osparc.po.Announcements", {
  extend: osparc.po.BaseView,

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "create-announcement":
          control = this.__createAnnouncements();
          this._add(control);
          break;
        case "announcement-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    _buildLayout: function() {
      this.getChildControl("create-announcement");
      this.getChildControl("announcement-container");
    },

    __createAnnouncements: function() {
      const announcementGroupBox = osparc.po.BaseView.createGroupBox(this.tr("Create announcement"));

      const announcementForm = this.__createAnnouncementForm();
      const form = new qx.ui.form.renderer.Single(announcementForm);
      announcementGroupBox.add(form);

      return announcementGroupBox;
    },

    __createAnnouncementForm: function() {
      const form = new qx.ui.form.Form();

      const title = new qx.ui.form.TextField().set({
        placeholder: this.tr("title")
      });
      form.add(title, this.tr("Title"));

      const description = new qx.ui.form.TextArea().set({
        placeholder: this.tr("description")
      });
      form.add(description, this.tr("Description"));

      const link = new qx.ui.form.TextField().set({
        placeholder: this.tr("link")
      });
      form.add(link, this.tr("Link"));

      // "widgets": ["login", "ribbon"],

      const widgetLogin = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetLogin, this.tr("Login"));

      const widgetRibbon = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetRibbon, this.tr("Ribbon"));

      const widgetUserMenu = new qx.ui.form.CheckBox().set({
        value: false
      });
      form.add(widgetUserMenu, this.tr("User Menu"));

      const generateAnnouncementBtn = new osparc.ui.form.FetchButton(this.tr("Generate"));
      generateAnnouncementBtn.set({
        appearance: "form-button"
      });
      generateAnnouncementBtn.addListener("execute", () => {
        const widgets = [];
        if (widgetLogin.getValue()) {
          widgets.push("login");
        }
        if (widgetRibbon.getValue()) {
          widgets.push("ribbon");
        }
        if (widgetUserMenu.getValue()) {
          widgets.push("user-menu");
        }
        const announcementData = {
          "id": osparc.utils.Utils.uuidV4(),
          "products": [osparc.product.Utils.getProductName()],
          "title": title.getValue(),
          "description": description.getValue(),
          "widgets": JSON.stringify(widgets),
          "start": "now",
          "end": "later",
        };
        this.__populateAnnouncementLayout(announcementData);
      }, this);
      form.addButton(generateAnnouncementBtn);

      return form;
    },

    __populateAnnouncementLayout: function(announcementData) {
      const vBox = this.getChildControl("announcement-container");
      vBox.removeAll();

      const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(10).set({
        alignY: "middle"
      }));
      vBox.add(hBox);

      const announcementField = new qx.ui.form.TextArea(announcementData).set({
        readOnly: true
      });
      hBox.add(announcementField);

      const copyAnnouncementBtn = new qx.ui.form.Button(this.tr("Copy announcement"));
      copyAnnouncementBtn.set({appearance: "form-button-outlined"});
      copyAnnouncementBtn.addListener("execute", () => {
        if (osparc.utils.Utils.copyTextToClipboard(announcementData)) {
          copyAnnouncementBtn.setIcon("@FontAwesome5Solid/check/12");
        }
      });
      hBox.add(copyAnnouncementBtn);

      const announcementRespViewer = new osparc.ui.basic.JsonTreeWidget(announcementData, "announcement-data");
      const container = new qx.ui.container.Scroll();
      container.add(announcementRespViewer);
      vBox.add(container, {
        flex: 1
      });
    }
  }
});
