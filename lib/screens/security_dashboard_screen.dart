import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../providers/app_providers.dart';

typedef VoidCallback = void Function();

class SecurityDashboardScreen extends ConsumerWidget {
  const SecurityDashboardScreen({
    super.key,
    required this.onBack,
  });

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(securityDashboardProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Security Dashboard'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: onBack,
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(
          children: [
            Wrap(
              spacing: 16,
              runSpacing: 16,
              children: [
                _KpiCard(
                  label: 'Total messages',
                  value: state.totalMessages.toString(),
                  icon: Icons.mail_outline,
                ),
                _KpiCard(
                  label: 'Valid signatures',
                  value: state.validSignatures.toString(),
                  icon: Icons.verified_outlined,
                  color: Colors.green,
                ),
                _KpiCard(
                  label: 'Failed signatures',
                  value: state.failedSignatures.toString(),
                  icon: Icons.error_outline,
                  color: Colors.red,
                ),
                _KpiCard(
                  label: 'PQC-enabled contacts',
                  value: state.pqcContacts.toString(),
                  icon: Icons.shield,
                  color: Colors.blue,
                ),
                _KpiCard(
                  label: 'Classical-only contacts',
                  value: state.classicalOnlyContacts.toString(),
                  icon: Icons.shield_outlined,
                  color: Colors.orange,
                ),
              ],
            ),
            const SizedBox(height: 24),
            Text(
              'Key management status',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(Icons.vpn_key),
                title: const Text('Local PQC key material'),
                subtitle: const Text(
                  'Managed by backend Python service. QMail UI shows high-level status only.',
                ),
                trailing: Chip(
                  label: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: const [
                      Icon(
                        Icons.check_circle_outline,
                        size: 16,
                      ),
                      SizedBox(width: 4),
                      Text('Healthy'),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(Icons.settings_remote),
                title: const Text('KM configuration'),
                subtitle: const Text(
                  'Configured by Python backend via API. Use this screen to surface read-only config and diagnostics.',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  // Placeholder for future KM configuration details.
                },
              ),
            ),
            const SizedBox(height: 8),
            Card(
              child: ListTile(
                leading: const Icon(Icons.fact_check),
                title: const Text('Recent verification results'),
                subtitle: const Text(
                  'Summarized view of recent signature verification events from the backend.',
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({
    required this.label,
    required this.value,
    required this.icon,
    this.color,
  });

  final String label;
  final String value;
  final IconData icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cardColor =
        color?.withOpacity(0.1) ?? theme.colorScheme.surfaceVariant;

    return SizedBox(
      width: 180,
      height: 110,
      child: Card(
        color: cardColor,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, color: color ?? theme.colorScheme.primary),
              const Spacer(),
              Text(
                value,
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                label,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

