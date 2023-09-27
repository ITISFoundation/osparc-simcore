/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.quickStart.ti.Dashboard", {
  extend: osparc.product.quickStart.SlideBase,

  construct: function() {
    const title = this.tr("Dashboard");
    this.base(arguments, title);
  },

  members: {
    _populateCard: function() {
      const introText = this.tr("\
        The Dashboard is your private hub which contains all of your Plans as well as Plans that have been shared with you. \
        From the Dashboard you are able to open your Plan or create a New Plan from scratch.\
      ");
      const intro = osparc.product.quickStart.Utils.createLabel(introText);
      this._add(intro);

      const image = new qx.ui.basic.Image("osparc/tutorial/ti/Dashboard.png").set({
        alignX: "center",
        scale: true,
        width: 738,
        height: 235
      });
      this._add(image);

      const newPlanText = this.tr("\
        1) New Plan: by clicking on this card a new study will be created and open.\
        The planning process will be presented in three successive steps that will be described more in detail in the following steps.\
      ");
      const newPlan = osparc.product.quickStart.Utils.createLabel(newPlanText);
      this._add(newPlan);

      const otherPlansText = this.tr("\
        2) The other cards are TI Plans that were already created by you or shared with you. You can reopen them to do further anaylisis \
        or by clicking three dots, on the top right corner, you can share, delete or check the details and metadata.\
      ");
      const otherPlans = osparc.product.quickStart.Utils.createLabel(otherPlansText);
      this._add(otherPlans);
    }
  }
});
