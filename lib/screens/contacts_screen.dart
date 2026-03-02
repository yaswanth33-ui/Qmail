import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/email_models.dart';
import '../providers/app_providers.dart';

typedef VoidCallback = void Function();

class ContactsScreen extends ConsumerWidget {
  const ContactsScreen({
    super.key,
    required this.onBack,
  });

  final VoidCallback onBack;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final contacts = ref.watch(contactsProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Contacts & Address Book'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: onBack,
        ),
      ),
      body: Column(
        children: [
          Padding(
            padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: TextField(
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: 'Search contacts…',
                border: OutlineInputBorder(),
                isDense: true,
              ),
              onChanged: (value) {
                // Hook up to a search/filter provider or backend API
                // when implementing full-text contact search.
              },
            ),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: contacts.length,
              itemBuilder: (context, index) {
                final c = contacts[index];
                return ListTile(
                  leading: CircleAvatar(
                    child: Text(
                      c.displayName.isNotEmpty
                          ? c.displayName[0]
                          : '?',
                    ),
                  ),
                  title: Text(c.displayName),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(c.email),
                      Text(
                        c.supportsPqc
                            ? 'Quantum-secure (PQC key stored)'
                            : 'Classical only',
                        style: TextStyle(
                          color: c.supportsPqc
                              ? Colors.green
                              : Colors.orange,
                        ),
                      ),
                    ],
                  ),
                  trailing: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      if (c.pqcPublicKey != null)
                        const Text(
                          'PQC',
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      if (c.groups.isNotEmpty)
                        Text(
                          c.groups.join(', '),
                          style: Theme.of(context)
                              .textTheme
                              .labelSmall,
                        ),
                    ],
                  ),
                  onTap: () {
                    // In a full app, this could open a contact detail
                    // view with options to edit keys and metadata.
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

