/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2026 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.po.EmailEditor", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox(5));

    this.__selectedGroupIds = [];
    this.__ccSelectedGroupIds = [];
    this.__bccSelectedGroupIds = [];

    this.__buildLayout();
  },

  statics: {
    ROWS: {
      "to": 0,
      "cc": 1,
      "bcc": 2,
    },
  },

  members: {
    __selectedGroupIds: null,
    __ccSelectedGroupIds: null,
    __bccSelectedGroupIds: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "form-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Grid(10, 5));
          control.getLayout().setColumnFlex(1, 1);
          this._add(control);
          break;
        }
        case "recipients-container-to":
        case "recipients-container-cc":
        case "recipients-container-bcc": {
          const type = id.replace("recipients-container-", "");
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
            alignY: "middle",
          })).set({
            backgroundColor: "input-background",
            height: 26,
            marginBottom: 5,
          });
          const formContainer = this.getChildControl("form-container");
          const row = this.self().ROWS[type];
          const labels = {
            "to": this.tr("To"),
            "cc": this.tr("Cc"),
            "bcc": this.tr("Bcc"),
          };
          formContainer.add(new qx.ui.basic.Label(labels[type]).set({
            paddingTop: 5,
          }), {
            row,
            column: 0
          });
          formContainer.add(control, {
            row,
            column: 1
          });
          break;
        }
        case "add-recipient-button-to":
        case "add-recipient-button-cc":
        case "add-recipient-button-bcc": {
          const type = id.replace("add-recipient-button-", "");
          control = new qx.ui.form.Button(null, "@FontAwesomeSolid/plus/12").set({
            allowGrowX: false,
            allowGrowY: true,
            toolTipText: this.tr("Add Recipient"),
          });
          control.addListener("execute", () => this.__openCollaboratorsManager(type), this);
          this.getChildControl("recipients-container-" + type).add(control);
          break;
        }
        case "recipients-chips-to":
        case "recipients-chips-cc":
        case "recipients-chips-bcc": {
          const type = id.replace("recipients-chips-", "");
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(4, 4).set({
            alignY: "middle",
          }));
          this.getChildControl("recipients-container-" + type).add(control, {
            flex: 1
          });
          break;
        }
        case "subject-field": {
          control = new qx.ui.form.TextField().set({
            marginBottom: 10
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("Subject")).set({
            paddingTop: 5,
          }), {
            row: 3,
            column: 0
          });
          formContainer.add(control, {
            row: 3,
            column: 1
          });
          break;
        }
        case "email-content-editor-and-preview": {
          control = new osparc.editor.EmailContentEditor();
          const container = new qx.ui.container.Scroll();
          container.add(control);
          this._add(container, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      ["to", "cc", "bcc"].forEach(type => {
        this.getChildControl("add-recipient-button-" + type);
        this.getChildControl("recipients-chips-" + type);
      });
      this.getChildControl("subject-field");
      this.getChildControl("email-content-editor-and-preview");
    },

    __getSelectedGroupIdsByType: function(type) {
      switch (type) {
        case "cc":
          return this.__ccSelectedGroupIds;
        case "bcc":
          return this.__bccSelectedGroupIds;
        default:
          return this.__selectedGroupIds;
      }
    },

    __openCollaboratorsManager: function(type) {
      const data = {
        resourceType: "emailRecipients",
      };
      const collaboratorsManager = new osparc.share.NewCollaboratorsManager(data, true, false);
      collaboratorsManager.getActionButton().setLabel(this.tr("Add"));
      collaboratorsManager.addListener("addCollaborators", e => {
        const data = e.getData();
        const selectedGids = data.selectedGids;
        const groupIds = this.__getSelectedGroupIdsByType(type);
        selectedGids.forEach(gid => {
          if (!groupIds.includes(gid)) {
            groupIds.push(gid);
          }
        });
        this.__updateRecipientsChips(type);
        collaboratorsManager.close();
      }, this);
    },

    clearRecipients: function() {
      this.__selectedGroupIds = [];
      this.__ccSelectedGroupIds = [];
      this.__bccSelectedGroupIds = [];
      ["to", "cc", "bcc"].forEach(type => this.__updateRecipientsChips(type));
    },

    __updateRecipientsChips: function(type) {
      const chipsContainer = this.getChildControl("recipients-chips-" + type);
      chipsContainer.removeAll();
      const groupsStore = osparc.store.Groups.getInstance();
      const groupIds = this.__getSelectedGroupIdsByType(type);
      groupIds.forEach((gid, index) => {
        const group = groupsStore.getGroup(gid);
        const chip = this.addChip(type, group.getLabel(), group.getDescription());
        chip.addListener("tap", () => {
          groupIds.splice(index, 1);
          this.__updateRecipientsChips(type);
        }, this);
      });
    },

    addChip: function(type, label, description) {
      const chip = new qx.ui.basic.Atom(label, "@FontAwesomeSolid/times/10").set({
        toolTipText: description,
        padding: [4, 8],
        decorator: "chip",
        cursor: "pointer",
        iconPosition: "right",
        gap: 8,
        allowGrowY: true,
        backgroundColor: "background-main-3",
      });
      const chipsContainer = this.getChildControl("recipients-chips-" + type);
      chipsContainer.add(chip);
      return chip;
    },

    getSelectedGroupIds: function() {
      return this.__selectedGroupIds;
    },

    getCcSelectedGroupIds: function() {
      return this.__ccSelectedGroupIds;
    },

    getBccSelectedGroupIds: function() {
      return this.__bccSelectedGroupIds;
    },
  }
});
