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

  construct: function(study) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.Canvas());

    this.__createLayout(study);
  },

  members: {
    __createLayout: function(study) {
      const shareStudyLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const withDataGrp = new qx.ui.groupbox.GroupBox(this.tr("Pipeline with Data"));
      withDataGrp.setLayout(new qx.ui.layout.VBox(5));

      const copyLinkLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const shareStudyCopyLinkTF = new qx.ui.form.TextField().set({
        readOnly: true
      });
      copyLinkLayout.add(shareStudyCopyLinkTF, {
        flex: 1
      });
      const copyLinkBtn = new qx.ui.form.Button(this.tr("Copy Link")).set({
        width: 100
      });
      copyLinkBtn.addListener("execute", function() {
        const shareStudyCopyLink = shareStudyCopyLinkTF.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyLink);
        shareStudyCopyLinkTF.selectAllText();
      });
      copyLinkLayout.add(copyLinkBtn);
      withDataGrp.add(copyLinkLayout);

      const copyTokenLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5));
      const shareStudyCopyTokenTF = new qx.ui.form.TextField().set({
        readOnly: true
      });
      copyTokenLayout.add(shareStudyCopyTokenTF, {
        flex: 1
      });
      const copyTokenBtn = new qx.ui.form.Button(this.tr("Copy Token")).set({
        width: 100
      });
      copyTokenBtn.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyCopyTokenTF.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyCopyTokenTF.selectAllText();
      });
      copyTokenLayout.add(copyTokenBtn);
      withDataGrp.add(copyTokenLayout);

      shareStudyLayout.add(withDataGrp);

      const withoutDataGrp = new qx.ui.groupbox.GroupBox(this.tr("Only pipeline"));
      withoutDataGrp.setLayout(new qx.ui.layout.HBox(5));
      const shareStudyCopyWorkbenchTA = new qx.ui.form.TextArea().set({
        height: 400,
        wrap: false,
        readOnly: true
      });
      withoutDataGrp.add(shareStudyCopyWorkbenchTA, {
        flex: 1
      });
      const copyWorkbenchBtn = new qx.ui.form.Button(this.tr("Copy Pipeline")).set({
        width: 100,
        allowGrowY: false
      });
      copyWorkbenchBtn.addListener("execute", function() {
        const shareStudyCopyToken = shareStudyCopyWorkbenchTA.getValue();
        osparc.utils.Utils.copyTextToClipboard(shareStudyCopyToken);
        shareStudyCopyWorkbenchTA.selectAllText();
      });
      withoutDataGrp.add(copyWorkbenchBtn);
      shareStudyLayout.add(withoutDataGrp);

      const params = {
        url: {
          "study_id": study.uuid
        }
      };
      osparc.data.Resources.getOne("shareStudy", params)
        .then(tokensList => {
          shareStudyCopyLinkTF.setValue(tokensList["copyLink"]);
          shareStudyCopyTokenTF.setValue(tokensList["copyToken"]);
          const workbenchPretty = JSON.stringify(tokensList["copyObject"], null, 4);
          shareStudyCopyWorkbenchTA.setValue(workbenchPretty);
        })
        .catch(err => console.error(err));

      this._add(shareStudyLayout, {
        top: 10,
        right: 10,
        bottom: 10,
        left: 10
      });
    }
  }
});
