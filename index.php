<?php
session_start();

// DATABASE SETUP (create if not exists)
$dbFile = __DIR__ . '/backup_admin.db';
$db = new PDO('sqlite:' . $dbFile);
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

// Create tables if they don't exist
$db->exec("CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)");
$db->exec("CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    total_files INTEGER,
    uploaded_files INTEGER,
    remote_path TEXT
)");

// Create default user if not exists (username: jocarsa, password: jocarsa)
// In production, always hash passwords
$stmt = $db->prepare("SELECT * FROM users WHERE username = ?");
$stmt->execute(['jocarsa']);
if (!$stmt->fetch(PDO::FETCH_ASSOC)) {
    $stmt = $db->prepare("INSERT INTO users (username, password) VALUES (?, ?)");
    // Using PHP's password_hash function
    $stmt->execute(['jocarsa', password_hash('jocarsa', PASSWORD_DEFAULT)]);
}

// ROUTING: Decide what to display based on "act" parameter.
$action = isset($_GET['act']) ? $_GET['act'] : '';

/**
 * Helper: Render the header and navigation.
 */
function render_header($title = 'Backup Admin Panel') {
    ?>
    <!DOCTYPE html>
    <html>
    <head>
        <title><?php echo htmlspecialchars($title); ?></title>
        <link rel="stylesheet" type="text/css" href="style.css">
        <script>
            // Function to poll progress and update the progress bar
            function checkProgress() {
                var xhr = new XMLHttpRequest();
                xhr.onreadystatechange = function() {
                    if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200) {
                        var percentage = parseFloat(xhr.responseText);
                        document.getElementById('progress-bar').style.width = percentage + '%';
                        document.getElementById('progress-text').innerHTML = percentage.toFixed(2) + '%';
                        if (percentage < 100) {
                            setTimeout(checkProgress, 1000);
                        }
                    }
                }
                xhr.open("GET", "index.php?act=progress", true);
                xhr.send();
            }
        </script>
    </head>
    <body>
    <div class="header">
        <h1>Backup Admin Panel</h1>
        <?php if (isset($_SESSION['username'])): ?>
            <p>Welcome, <?php echo htmlspecialchars($_SESSION['username']); ?> | <a href="index.php?act=logout">Logout</a></p>
        <?php endif; ?>
    </div>
    <div class="sidebar">
        <?php if (isset($_SESSION['username'])): ?>
            <a href="index.php">Dashboard</a>
            <a href="index.php?act=backups">Backup History</a>
        <?php endif; ?>
    </div>
    <div class="content">
    <?php
}

/**
 * Helper: Render footer.
 */
function render_footer() {
    ?>
    </div><!-- .content -->
    </body>
    </html>
    <?php
}

// ACTION: Login (if not logged in and not doing logout or AJAX actions)
if ($action === 'login' || (!isset($_SESSION['username']) && $action !== 'progress')) {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        // Process login
        $username = trim($_POST['username']);
        $password = $_POST['password'];
        $stmt = $db->prepare("SELECT * FROM users WHERE username = ?");
        $stmt->execute([$username]);
        $user = $stmt->fetch(PDO::FETCH_ASSOC);
        if ($user && password_verify($password, $user['password'])) {
            $_SESSION['username'] = $username;
            header("Location: index.php");
            exit();
        } else {
            $error = "Invalid credentials.";
        }
    }
    // Show login form
    render_header("Admin Login");
    ?>
    <div class="login-container">
        <h2>Admin Login</h2>
        <?php if (isset($error)): ?>
            <p class="error"><?php echo htmlspecialchars($error); ?></p>
        <?php endif; ?>
        <form method="post" action="index.php?act=login">
            <input type="text" name="username" placeholder="Username" required autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <input type="submit" value="Login">
        </form>
    </div>
    <?php
    render_footer();
    exit();
}

// ACTION: Logout
if ($action === 'logout') {
    session_destroy();
    header("Location: index.php");
    exit();
}

// ACTION: AJAX Progress (no header/footer)
if ($action === 'progress') {
    // Simply read and output the content of progress.txt
    if (file_exists("progress.txt")) {
        echo file_get_contents("progress.txt");
    } else {
        echo "0";
    }
    exit();
}

// ACTION: Run backup (launch python script)
if ($action === 'run_backup') {
    // Launch the backup process in the background
    $python = "/usr/bin/python3"; // adjust as needed
    $script = __DIR__ . "/backup.py"; // adjust as needed
    exec("$python $script > /dev/null 2>&1 &");
    header("Location: index.php");
    exit();
}

// Default Action: Dashboard
if ($action === '') {
    render_header("Dashboard");
    ?>
    <h2>Dashboard</h2>
    <form method="post" action="index.php?act=run_backup">
        <input type="submit" value="Start Backup Process">
    </form>
    <div class="progress">
        <div id="progress-bar" class="progress-bar"></div>
    </div>
    <p id="progress-text">0%</p>
    <button onclick="checkProgress()">Check Progress</button>
    <?php
    render_footer();
    exit();
}

// ACTION: Display Backup History
if ($action === 'backups') {
    render_header("Backup History");
    ?>
    <h2>Backup History</h2>
    <?php
    // Fetch backup records from database
    $stmt = $db->query("SELECT * FROM backups ORDER BY timestamp DESC");
    $backups = $stmt->fetchAll(PDO::FETCH_ASSOC);
    if ($backups):
        ?>
        <table>
            <tr>
                <th>ID</th>
                <th>Timestamp</th>
                <th>Total Files</th>
                <th>Uploaded Files</th>
                <th>Remote Path</th>
                <th>Actions</th>
            </tr>
            <?php foreach ($backups as $backup): ?>
                <tr>
                    <td><?php echo $backup['id']; ?></td>
                    <td><?php echo htmlspecialchars($backup['timestamp']); ?></td>
                    <td><?php echo $backup['total_files']; ?></td>
                    <td><?php echo $backup['uploaded_files']; ?></td>
                    <td><?php echo htmlspecialchars($backup['remote_path']); ?></td>
                    <td>
                        <!-- For delete action (simple example) -->
                        <a href="index.php?act=delete_backup&id=<?php echo $backup['id']; ?>" onclick="return confirm('Are you sure?')">Delete</a>
                    </td>
                </tr>
            <?php endforeach; ?>
        </table>
    <?php else: ?>
        <p>No backups found.</p>
    <?php endif;
    render_footer();
    exit();
}

// ACTION: Delete a backup record (simple delete, no confirmation page)
if ($action === 'delete_backup' && isset($_GET['id'])) {
    $id = intval($_GET['id']);
    $stmt = $db->prepare("DELETE FROM backups WHERE id = ?");
    $stmt->execute([$id]);
    header("Location: index.php?act=backups");
    exit();
}

// If an unknown action is passed, show dashboard.
header("Location: index.php");
exit();
?>

