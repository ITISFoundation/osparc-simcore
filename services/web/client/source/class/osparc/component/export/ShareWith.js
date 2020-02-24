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
 * View that shows who you want to share the resource with:
 * - Everyone
 * - My organizations
 * - Private
 */

qx.Class.define("osparc.component.export.ShareWith", {
  extend: qx.ui.groupbox.GroupBox,

  construct: function() {
    this.base(arguments, this.tr("Share with"));

    this.set({
      appearance: "settings-groupbox",
      layout: new qx.ui.layout.VBox(10)
    });

    this.__buildLayout();
  },

  properties: {
    ready: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeReady"
    }
  },

  members: {
    __rbManager: null,

    __buildLayout: function() {
      var allRB = new qx.ui.form.RadioButton(this.tr("Everyone"));
      var organizationsRB = new qx.ui.form.RadioButton(this.tr("Organizations"));
      var noneRB = new qx.ui.form.RadioButton(this.tr("Private"));

      this.add(allRB);
      this.add(organizationsRB);
      this.add(noneRB);

      // Add all radio buttons to the manager
      this.__rbManager = new qx.ui.form.RadioGroup(allRB, organizationsRB, noneRB).set({
        allowEmptySelection: true
      });
      this.__rbManager.addListener("changeSelection", this.__onChangeSelection, this);
      this.__rbManager.setSelection([]);
    },

    __onChangeSelection: function() {
      this.setReady(Boolean(this.__rbManager.getSelection().length));
    }
  }
});
