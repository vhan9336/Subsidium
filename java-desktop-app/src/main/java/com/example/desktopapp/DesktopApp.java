package com.example.desktopapp;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.event.ActionEvent;
import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JPanel;
import javax.swing.SwingConstants;
import javax.swing.SwingUtilities;

public class DesktopApp {
    private DesktopApp() {
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(DesktopApp::openWindow);
    }

    private static void openWindow() {
        JFrame frame = new JFrame("My Desktop App");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setMinimumSize(new Dimension(420, 260));
        frame.setLocationByPlatform(true);

        JPanel content = new JPanel(new BorderLayout(12, 16));
        content.setBorder(BorderFactory.createEmptyBorder(32, 36, 28, 36));
        content.setBackground(new Color(248, 250, 252));

        JLabel title = new JLabel("Hello, desktop!", SwingConstants.CENTER);
        title.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 26));
        title.setForeground(new Color(30, 41, 59));

        JLabel message = new JLabel("Your Java app is running in its own window.", SwingConstants.CENTER);
        message.setFont(new Font(Font.SANS_SERIF, Font.PLAIN, 14));
        message.setForeground(new Color(71, 85, 105));

        JButton button = new JButton("Get started");
        button.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 14));
        button.addActionListener((ActionEvent event) -> {
            message.setText("You're all set. Customize this app to make it yours!");
        });

        JPanel center = new JPanel(new BorderLayout(8, 12));
        center.setOpaque(false);
        center.add(title, BorderLayout.NORTH);
        center.add(message, BorderLayout.CENTER);

        JPanel footer = new JPanel();
        footer.setOpaque(false);
        footer.add(button);

        content.add(center, BorderLayout.CENTER);
        content.add(footer, BorderLayout.SOUTH);
        frame.setContentPane(content);
        frame.pack();
        frame.setVisible(true);
    }
}
