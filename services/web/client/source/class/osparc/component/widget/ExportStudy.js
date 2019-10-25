/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that provides the form for sharing a study
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   const shareStudy = new osparc.component.widget.ShareStudy(study);
 *   this.getRoot().add(shareStudy);
 * </pre>
 */

qx.Class.define("osparc.component.widget.ExportStudy", {
  extend: qx.ui.core.Widget,

  construct: function(studyModel, wbObject) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.__createLayout(studyModel, wbObject);
  },

  members: {
    __createLayout: function(studyModel, wbObject) {
      const shareStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const box11 = new qx.ui.groupbox.GroupBox(this.tr("Export study: Pipeline + Data"));
      box11.setLayout(new qx.ui.layout.HBox(5));
      const shareStudyCopyTF = new qx.ui.form.TextField().set({
        readOnly: true
      });
      box11.add(shareStudyCopyTF, {
        flex: 1
      });
      const copyLinkBtn1 = new qx.ui.form.Button(this.tr("Copy Link"));
      copyLinkBtn1.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyCopyTF.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyCopyTF.selectAllText();
      });
      const params = {
        url: {
          "study_id": studyModel.getUuid()
        }
      };
      osparc.data.Resources.getOne("shareStudy", params)
        .then(tokensList => {
          shareStudyCopyTF.setValue(tokensList["copy"]);
        })
        .catch(err => console.error(err));
      box11.add(copyLinkBtn1);
      shareStudyLayout.add(box11);


      const box12 = new qx.ui.groupbox.GroupBox(this.tr("Export study: Only pipeline"));
      box12.setLayout(new qx.ui.layout.HBox(5));
      const wbPretty = JSON.stringify(wbObject, null, 4);
      const shareStudyCopyWorkbenchTA = new qx.ui.form.TextArea(wbPretty).set({
        height: 400,
        wrap: false,
        readOnly: true
      });
      box12.add(shareStudyCopyWorkbenchTA, {
        flex: 1
      });
      const copyLinkBtn2 = new qx.ui.form.Button(this.tr("Copy Pipeline")).set({
        allowGrowY: false
      });
      copyLinkBtn2.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyCopyWorkbenchTA.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyCopyWorkbenchTA.selectAllText();
      });
      box12.add(copyLinkBtn2);
      shareStudyLayout.add(box12);

      this._add(shareStudyLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
