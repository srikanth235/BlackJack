/* Functions for adding listeners end here */
function addInputActionListener() {
	$("#hit")
			.on(
					"click",
					function() {
						$(
								"<img id = 'player_first'  src = 'images/deck/10c.png' align = 'center'/>")
								.appendTo('#player');
						$(
								"<img id = 'player_first'  src = 'images/deck/10c.png' align = 'center'/>")
								.appendTo('#dealer');
					});

	$("#stand").on("click", function() {
		alert("here");
	});

	$("#double").on("click", function() {
		alert("here");
	});
}

$(document).ready(function() {
	addInputActionListener();
});