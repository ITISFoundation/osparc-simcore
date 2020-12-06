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
 * Widget that displays a score in form of stars.
 * It can also show the score with the max score next to it "87/100"
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
      init: 1,
      nullable: false,
      apply: "__applyScore"
    },

    maxScore: {
      check: "Number",
      init: 5,
      nullable: false,
      apply: "__applyMaxScore"
    },

    nStars: {
      check: "Number",
      init: 5,
      nullable: false,
      apply: "__applyNStars"
    }
  },

  statics: {
    StarFull: "FontAwesome5Solid/star/12",
    StarHalf: "FontAwesome5Solid/star-half-alt/12",
    StarEmpty: "FontAwesome5Regular/star/12"
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
      const maxScore = this.getMaxScore();
      if (value && value >= 0 && value <= maxScore) {
        this.__renderStars();
      }
    },

    __applyMaxScore: function(value) {
      const score = this.getScore();
      if (value && score >= 0 && score <= value) {
        this.__renderStars();
      }
    },

    __applyNStars: function(value) {
      const score = this.getScore();
      const maxScore = this.getMaxScore();
      if (score >= 0 && score <= maxScore) {
        this.__renderStars();
      }
    },

    __renderStars: function() {
      const score = this.getScore();
      const maxScore = this.getMaxScore();
      if (score && maxScore && score >= 0 && score <= maxScore) {
        const maxStars = this.getNStars();
        const normScore = score/maxScore;
        const fullStars = Math.floor(normScore/(1.0/maxStars));
        const halfStar = Math.round((normScore%(1.0/maxStars))*maxStars);
        const emptyStars = maxStars - fullStars - halfStar;
        const starsLayout = this.getChildControl("stars-layout");
        for (let i=0; i<fullStars; i++) {
          const star = new qx.ui.basic.Image(this.self().StarFull);
          starsLayout.add(star);
        }
        for (let i=0; i<halfStar; i++) {
          const star = new qx.ui.basic.Image(this.self().StarHalf);
          starsLayout.add(star);
        }
        for (let i=0; i<emptyStars; i++) {
          const star = new qx.ui.basic.Image(this.self().StarEmpty);
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
