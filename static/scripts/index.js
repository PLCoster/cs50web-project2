document.addEventListener('DOMContentLoaded', () => {

  let screen_name;

  // Connect to websocket
  var socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

  // When connected, run script:
  socket.on('connect', () => {

    // Function to set up sending messages to the server:
    const message_config = function () {
      // Each button should emit a "submit vote" event
      document.querySelectorAll('#vote > button').forEach(button => {
        button.onclick = () => {
            event.preventDefault();
            const selection = button.dataset.vote;
            socket.emit('submit vote', {'selection': selection, 'screen_name': screen_name});
        };
      });
    };


    // Check local storage for username, if none, ask for a username:
    if (!localStorage.getItem('screen_name')) {
      document.querySelector('#login').style.display = "block";
      document.querySelector('#vote').style.display = "none";
    } else {
      screen_name = localStorage.getItem('screen_name')
      document.querySelector('#login').style.display = "none";
      message_config();
    }


    // Log in button should set username and then hide login and display vote buttons
    document.querySelector('#login').onsubmit = () => {
      event.preventDefault();
      if (document.querySelector('#login-screen_name').value) {
        localStorage.setItem('screen_name', document.querySelector('#login-screen_name').value);
        screen_name = localStorage.getItem('screen_name');
        message_config();

        // Hide Login Form and Reveal Vote Buttons:
        document.querySelector('#login').style.display = "none";
        document.querySelector('#vote').style.display = "inline";
        }
      };

       // When a new vote is announced, add to the unordered list
    socket.on('announce vote', data => {
      console.log('vote broadcast received, vote data:', data)

      const li = document.createElement('li');
      li.innerHTML = `${data.screen_name}'s vote recorded: ${data.selection}`;
      document.querySelector('#votes').append(li);
    });

  });

});