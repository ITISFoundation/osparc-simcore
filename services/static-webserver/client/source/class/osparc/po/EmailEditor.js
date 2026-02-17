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

    this.__buildLayout();
  },

  members: {
    __selectedGroupIds: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "form-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Grid(10, 5));
          control.getLayout().setColumnFlex(1, 1);
          this._add(control);
          break;
        }
        case "recipients-container": {
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(6).set({
            alignY: "middle",
          })).set({
            backgroundColor: "input-background",
            height: 26,
            marginBottom: 5,
          });
          const formContainer = this.getChildControl("form-container");
          formContainer.add(new qx.ui.basic.Label(this.tr("To")).set({
            paddingTop: 5,
          }), {
            row: 0,
            column: 0
          });
          formContainer.add(control, {
            row: 0,
            column: 1
          });
          break;
        }
        case "add-recipient-button": {
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/plus/12").set({
            allowGrowX: false,
            allowGrowY: true,
            toolTipText: this.tr("Add Recipient"),
          });
          control.addListener("execute", () => this.__openCollaboratorsManager(), this);
          this.getChildControl("recipients-container").add(control);
          break;
        }
        case "recipients-chips": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Flow(4, 4).set({
            alignY: "middle",
          }));
          this.getChildControl("recipients-container").add(control, {
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
            row: 1,
            column: 0
          });
          formContainer.add(control, {
            row: 1,
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
      this.getChildControl("add-recipient-button");
      this.getChildControl("recipients-chips");
      this.getChildControl("subject-field");
      this.getChildControl("email-content-editor-and-preview");
    },

    __openCollaboratorsManager: function() {
      const data = {
        resourceType: "emailRecipients",
      };
      const collaboratorsManager = new osparc.share.NewCollaboratorsManager(data, true, false);
      collaboratorsManager.getActionButton().setLabel(this.tr("Add"));
      collaboratorsManager.addListener("addCollaborators", e => {
        const data = e.getData();
        const selectedGids = data.selectedGids;
        selectedGids.forEach(gid => {
          if (!this.__selectedGroupIds.includes(gid)) {
            this.__selectedGroupIds.push(gid);
          }
        });
        this.__updateRecipientsChips();
        collaboratorsManager.close();
      }, this);
    },

    __updateRecipientsChips: function() {
      const chipsContainer = this.getChildControl("recipients-chips");
      chipsContainer.removeAll();
      const groupsStore = osparc.store.Groups.getInstance();
      this.__selectedGroupIds.forEach((gid, index) => {
        const group = groupsStore.getGroup(gid);
        const chip = new qx.ui.basic.Atom(group.getLabel(), "@FontAwesome5Solid/times/10").set({
          toolTipText: group.getDescription(),
          padding: [4, 8],
          decorator: "chip",
          cursor: "pointer",
          iconPosition: "right",
          gap: 8,
          allowGrowY: true,
          backgroundColor: "background-main-3",
        });
        chip.addListener("tap", () => {
          this.__selectedGroupIds.splice(index, 1);
          this.__updateRecipientsChips();
        }, this);
        chipsContainer.add(chip);
      });
    },

    getSelectedGroupIds: function() {
      return this.__selectedGroupIds;
    },
  }
});
