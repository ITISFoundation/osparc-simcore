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
 * App/theme dependant logo
 */
qx.Class.define("osparc.ui.basic.StarsRating", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());
  },

  properties: {
    score: {
      check: "Number",
      init: 0,
      nullable: false,
      apply: "__applyScore"
    },

    maxScore: {
      check: "Number",
      init: 1,
      nullable: false
    }
  },

  members: {
    // overridden
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "stars-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox());
          break;
        case "score-text": {
          control = new qx.ui.basic.Label();
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __applyScore: function(value) {
      if (value && value >= 0 && value <= 1) {
        const starsLayout = this.getChildControl("stars-layout");
        for (let i=0; i<value*5; i++) {
          const star = new qx.ui.basic.Image("FontAwesome5Solid/star/12");
          starsLayout.add(star);
        }
      }
    },

    showScore: function(show) {
      const scoreText = this.getChildControl("score-text");
      if (show) {
        const score = this.getScore();
        const maxScore = this.getMaxScore();
        scoreText.setValue(`${toString(score)}/${toString(maxScore)}`);
        scoreText.show();
      } else {
        scoreText.exclude();
      }
    }
  }
});
